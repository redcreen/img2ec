"""Celery 任务：处理单张原图，同步 DB 状态。"""
import random
from pathlib import Path

from img2ec.celery_app import celery_app
from img2ec.config import get_settings
from img2ec.core.pipeline import process_one_image
from img2ec.db import SessionLocal
from img2ec.infra.comfy_client import ComfyClient, ComfyError
from img2ec.infra.fs_layout import sku_dir as sku_dir_fn, ensure_sku_dirs
from img2ec.models import Project, SKU, SKUStatus, SourceImage, ImageStatus, Scene, PlatformOutputCopy


WORKFLOWS_DIR = Path(__file__).parents[2] / "workflows"


class CancelRequested(Exception):
    """User-requested cancel signal, propagated up through the pipeline."""


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_image_task(self, image_id: str, ratios: list[str] | None = None) -> str:
    settings = get_settings()
    db = SessionLocal()
    sku: SKU | None = None
    try:
        img: SourceImage | None = db.get(SourceImage, image_id)
        if img is None:
            return "missing"

        sku = db.get(SKU, img.sku_id)
        project: Project = db.get(Project, sku.project_id)
        scene: Scene | None = db.get(Scene, sku.scene_id) if sku.scene_id else None
        if scene is None:
            img.status = ImageStatus.FAILED.value
            img.err_msg = "no scene assigned to SKU"
            db.commit()
            return "no_scene"

        # 用户在 SKU 排队等待时就点了 cancel？直接 bail
        db.refresh(sku)
        if sku.status == "cancelled":
            img.status = ImageStatus.FAILED.value
            img.err_msg = "cancelled by user"
            db.commit()
            return "cancelled"

        skud = sku_dir_fn(Path(project.root_path).parent, project.name, sku.name)
        ensure_sku_dirs(skud)

        client = ComfyClient(settings.comfy_url, timeout=settings.comfy_timeout)

        def update_progress(stage: str, pct: int) -> None:
            img.status = stage if stage in ("cutting", "generating", "composing") else img.status
            img.progress = pct
            db.commit()

        def on_master_done(key: str, master_path: Path, idx: int, total: int) -> None:
            """每完成一张 master：① 写入 master_paths（前端轮询能立刻看到缩略图）
            ② 检查 SKU 是否被 cancel（用户随时可停止）"""
            img.master_paths = {**(img.master_paths or {}), key: str(master_path)}
            db.commit()
            db.refresh(sku)
            if sku.status == "cancelled":
                raise CancelRequested(f"cancel detected after master {idx}/{total}")

        try:
            derived = process_one_image(
                src_path=Path(img.src_path),
                sku_dir=skud,
                image_stem=Path(img.name).stem,
                scene_prompt=scene.prompt,
                scene_neg=scene.negative_prompt,
                ip_weight=scene.ip_adapter_weight,
                seed=random.randint(1, 2**31 - 1),
                comfy_client=client,
                workflows_dir=WORKFLOWS_DIR,
                on_progress=update_progress,
                on_master_done=on_master_done,
                ratios=ratios,
            )
            # 派生：合并新生成的 paths 到已有的（partial generation 累加）
            new_derived = {
                f"{plat}/{p.name}": str(p)
                for plat, paths in derived.items()
                for p in paths
            }
            img.derived_paths = {**(img.derived_paths or {}), **new_derived}
            # master_paths 已通过 on_master_done 增量写入；此处不再覆盖
            img.status = ImageStatus.DONE.value
            img.progress = 100
            db.commit()
        except CancelRequested:
            img.status = ImageStatus.FAILED.value
            img.err_msg = "cancelled by user"
            db.commit()
            return "cancelled"
        except ComfyError as e:
            img.status = ImageStatus.FAILED.value
            img.err_msg = str(e)
            db.commit()
            return "failed_comfy"
        except Exception as e:
            img.status = ImageStatus.FAILED.value
            img.err_msg = f"{type(e).__name__}: {e}"
            db.commit()
            return "failed"
        finally:
            client.close()

        # Phase 2.5: 文案生成（仅在 SKU 全部图都 done 且尚无 copy 时）
        db.refresh(sku)
        images = list(sku.images)
        all_done = all(i.status == ImageStatus.DONE.value for i in images)
        existing_copy = db.query(PlatformOutputCopy).filter_by(sku_id=sku.id).count()
        if all_done and existing_copy == 0 and images:
            try:
                from img2ec.core.copy_gen import generate_copy_for_sku
                from img2ec.infra.llm_provider import CodexCLIProvider, LLMProviderError
                # 用第一张已 done 的 master 1x1 做识别基准（最方正）
                first_img = images[0]
                master_1x1 = first_img.master_paths.get("1x1") if first_img.master_paths else None
                if master_1x1:
                    provider = CodexCLIProvider()
                    try:
                        result = generate_copy_for_sku(
                            provider=provider,
                            image_path=Path(master_1x1),
                            sku_name=sku.name,
                            scene_name=scene.name if scene else "",
                            scene_category=scene.category if scene else "",
                        )
                        _persist_copy(db, sku.id, result)
                        _render_detail_pages(
                            db, sku.id, skud, Path(img.name).stem, img.master_paths or {}
                        )
                    except LLMProviderError:
                        pass
            except Exception:
                pass

        return "done"
    finally:
        # 不论成功/失败/异常，都重新聚合 SKU 状态 —— 防止"卡 running"。
        # 用户主动 cancel 优先级最高，不被覆盖。
        try:
            if sku is not None:
                db.refresh(sku)
                if sku.status != "cancelled":
                    sku.status = _aggregate_sku_status(sku, db)
                    db.commit()
        except Exception:
            pass
        db.close()


def _aggregate_sku_status(sku: SKU, db) -> str:
    images = db.query(SourceImage).filter_by(sku_id=sku.id).all()
    statuses = {i.status for i in images}
    if statuses & {ImageStatus.PENDING.value, ImageStatus.CUTTING.value,
                   ImageStatus.GENERATING.value, ImageStatus.COMPOSING.value}:
        return SKUStatus.RUNNING.value
    if ImageStatus.FAILED.value in statuses:
        return SKUStatus.ERROR.value
    if statuses == {ImageStatus.DONE.value}:
        return SKUStatus.DONE.value
    return SKUStatus.READY.value


def _persist_copy(db, sku_id: str, result: dict) -> None:
    import uuid
    from img2ec.models import Platform, PlatformOutputCopy

    for plat_key in ("douyin", "shipinhao"):
        d = result.get(plat_key, {})
        db.add(PlatformOutputCopy(
            id=str(uuid.uuid4()), sku_id=sku_id, platform=plat_key,
            title=d.get("title", ""), subtitle=d.get("subtitle", ""),
            selling_points=d.get("selling_points", []),
            description_md=d.get("description_md", ""),
            category_path=d.get("category_path", ""),
            keywords=d.get("keywords", []), hashtags=[],
            video_script=d.get("video_script", ""),
            raw_response=d,
        ))
    xhs = result.get("xiaohongshu", {})
    db.add(PlatformOutputCopy(
        id=str(uuid.uuid4()), sku_id=sku_id, platform=Platform.XIAOHONGSHU.value,
        title=xhs.get("post_title", ""), subtitle="",
        selling_points=xhs.get("selling_points", []),
        description_md=xhs.get("post_body", ""),
        category_path="", keywords=[], hashtags=xhs.get("hashtags", []),
        video_script=xhs.get("video_script", ""),
        raw_response=xhs,
    ))
    db.commit()


def _render_detail_pages(db, sku_id: str, sku_dir: Path, _image_stem: str, master_paths: dict) -> None:
    """产品级详情页：3 平台各 1 张，文件名固定 detail-template.jpg（跨变体共享）。
    多变体时自动追加 color_comparison module。
    """
    from img2ec.core.detail_page import render_detail_page
    from img2ec.core.detail_template import DEFAULT_TEMPLATE
    from img2ec.infra.fs_layout import platform_dir as platform_dir_fn
    from img2ec.models import PlatformOutputCopy, SKU

    images = {k: Path(v) for k, v in master_paths.items()}
    if "1x1" not in images:
        return

    # 收集多变体颜色对比用的数据
    sku = db.get(SKU, sku_id)
    variants_meta: list[dict] = []
    if sku and len(sku.variants) > 1:
        for v in sku.variants:
            v_img = v.images[0] if v.images else None
            m_1x1 = (v_img.master_paths or {}).get("1x1") if v_img else None
            if m_1x1:
                variants_meta.append({"color_name": v.color_name, "image_path": Path(m_1x1)})

    template = dict(DEFAULT_TEMPLATE)
    template["modules"] = list(DEFAULT_TEMPLATE["modules"])
    if len(variants_meta) >= 2:
        # 在 selling_points 之后插入 color_comparison
        new_mods = []
        for m in template["modules"]:
            new_mods.append(m)
            if m.get("type") == "selling_points":
                new_mods.append({"type": "color_comparison", "config": {}})
        template["modules"] = new_mods

    copy_records = {c.platform: c for c in db.query(PlatformOutputCopy).filter_by(sku_id=sku_id).all()}
    for platform in ("douyin", "shipinhao", "xiaohongshu"):
        copy_row = copy_records.get(platform)
        if copy_row is None:
            continue
        copy_dict = {
            "title": copy_row.title,
            "subtitle": copy_row.subtitle,
            "selling_points": copy_row.selling_points or [],
        }
        try:
            out_path = platform_dir_fn(sku_dir, platform) / "detail-template.jpg"
            render_detail_page(
                template=template,
                copy=copy_dict,
                images=images,
                output_path=out_path,
                variants=variants_meta,
            )
        except Exception:
            pass
