"""Celery 任务：处理单张原图，同步 DB 状态。"""
from pathlib import Path

from img2ec.celery_app import celery_app
from img2ec.config import get_settings
from img2ec.core.pipeline import process_one_image
from img2ec.db import SessionLocal
from img2ec.infra.comfy_client import ComfyClient, ComfyError
from img2ec.infra.fs_layout import sku_dir as sku_dir_fn, ensure_sku_dirs
from img2ec.models import Project, SKU, SKUStatus, SourceImage, ImageStatus, Scene, PlatformOutputCopy


WORKFLOWS_DIR = Path(__file__).parents[2] / "workflows"


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def process_image_task(self, image_id: str) -> str:
    settings = get_settings()
    db = SessionLocal()
    try:
        img: SourceImage | None = db.get(SourceImage, image_id)
        if img is None:
            return "missing"

        sku: SKU = db.get(SKU, img.sku_id)
        project: Project = db.get(Project, sku.project_id)
        scene: Scene | None = db.get(Scene, sku.scene_id) if sku.scene_id else None
        if scene is None:
            img.status = ImageStatus.FAILED.value
            img.err_msg = "no scene assigned to SKU"
            db.commit()
            return "no_scene"

        skud = sku_dir_fn(Path(project.root_path).parent, project.name, sku.name)
        ensure_sku_dirs(skud)

        client = ComfyClient(settings.comfy_url, timeout=settings.comfy_timeout)

        def update_progress(stage: str, pct: int) -> None:
            img.status = stage if stage in ("cutting", "generating", "composing") else img.status
            img.progress = pct
            db.commit()

        try:
            derived = process_one_image(
                src_path=Path(img.src_path),
                sku_dir=skud,
                image_stem=Path(img.name).stem,
                scene_prompt=scene.prompt,
                scene_neg=scene.negative_prompt,
                ip_weight=scene.ip_adapter_weight,
                seed=42,
                comfy_client=client,
                workflows_dir=WORKFLOWS_DIR,
                on_progress=update_progress,
            )
            # derived 现在是 {platform: [paths]} 而不是 {platform: path}
            img.derived_paths = {
                f"{plat}/{p.name}": str(p)
                for plat, paths in derived.items()
                for p in paths
            }
            img.master_paths = {
                key: str(skud / "master" / f"{Path(img.name).stem}-{key}.jpg")
                for key in ("1x1", "long", "3x4", "9x16", "16x9")
            }
            img.status = ImageStatus.DONE.value
            img.progress = 100
            db.commit()
        except ComfyError as e:
            img.status = ImageStatus.FAILED.value
            img.err_msg = str(e)
            db.commit()
            raise self.retry(exc=e)
        except Exception as e:
            img.status = ImageStatus.FAILED.value
            img.err_msg = f"{type(e).__name__}: {e}"
            db.commit()
            raise
        finally:
            client.close()

        # Phase 2.5: 文案生成（仅在 SKU 全部图都 done 且尚无 copy 时）
        images = db.query(SourceImage).filter_by(sku_id=sku.id).all()
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
                        # Persist
                        _persist_copy(db, sku.id, result)
                    except LLMProviderError as e:
                        # 文案失败不阻塞图片输出
                        # TODO: 记录到 SKU 上一个 warning 字段（V1.1）
                        pass
            except Exception:
                pass

        # 聚合 SKU 状态
        sku.status = _aggregate_sku_status(sku, db)
        db.commit()
        return "done"
    finally:
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
            raw_response=d,
        ))
    xhs = result.get("xiaohongshu", {})
    db.add(PlatformOutputCopy(
        id=str(uuid.uuid4()), sku_id=sku_id, platform=Platform.XIAOHONGSHU.value,
        title=xhs.get("post_title", ""), subtitle="",
        selling_points=xhs.get("selling_points", []),
        description_md=xhs.get("post_body", ""),
        category_path="", keywords=[], hashtags=xhs.get("hashtags", []),
        raw_response=xhs,
    ))
    db.commit()
