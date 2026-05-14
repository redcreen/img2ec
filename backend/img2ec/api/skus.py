import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from img2ec.config import get_settings
from img2ec.db import get_session
from img2ec.infra.fs_layout import sku_dir, ensure_sku_dirs, source_dir
from img2ec.models import Project, SKU, SKUStatus, SourceImage, ImageStatus, Variant
from img2ec.schemas.sku import SKUCreate, SKUDimensions, SKUOut

router = APIRouter(prefix="/api/projects/{project_id}/skus", tags=["skus"])


def _path_to_url(path: str | None) -> str | None:
    """Convert an absolute filesystem path under root_path to a /static/projects/... URL.
    URL-encodes path segments so `#`, `?`, spaces 等特殊字符在浏览器里能正确发请求（不被解析为 fragment/query）。"""
    if not path:
        return None
    root = str(get_settings().root_path)
    if path.startswith(root):
        rel = path[len(root):].lstrip("/")
        from urllib.parse import quote
        # 按 / 分段后逐段 quote，避免把分隔符也编码掉
        encoded = "/".join(quote(seg, safe="") for seg in rel.split("/"))
        return f"/static/projects/{encoded}"
    return None


DIMENSION_STYLES = ("white", "template")


def _dimension_image_path_for_variant(variant, style: str = "white", image_idx: int = 0) -> Path | None:
    """Variant 维度的尺寸图路径（按 image_idx 选 source）。
    文件名 = <该 source 的 stem>-dimension-<style>.jpg，所以多 source 不会冲突。
    """
    if not variant or not variant.images:
        return None
    if image_idx < 0 or image_idx >= len(variant.images):
        return None
    sku = variant.product
    if sku is None:
        return None
    proj = sku.project
    if proj is None:
        return None
    if style not in DIMENSION_STYLES:
        return None
    from img2ec.infra.fs_layout import variant_dir as variant_dir_fn
    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name, sku.id)
    vdir = variant_dir_fn(skud, variant)
    image_stem = Path(variant.images[image_idx].name).stem
    return vdir / "outputs" / "dimension" / f"{image_stem}-dimension-{style}.jpg"


# 尺寸图状态已迁到 Redis（infra.state_store）；这里只是为兼容 import 名而保留空 dict
_DIM_STATE: dict[str, dict[str, dict]] = {}


def _enrich_variant(variant) -> dict:
    """序列化一个 variant 并注入计算字段（图片 URL、尺寸图 URL/状态）。"""
    from img2ec.schemas.sku import VariantOut
    out = VariantOut.model_validate(variant).model_dump()
    paths = variant.sku_thumb_paths or ([variant.sku_thumb_path] if variant.sku_thumb_path else [])
    out["sku_thumb_paths"] = paths
    out["sku_thumb_urls"] = [_path_to_url(p) or "" for p in paths]
    primary = variant.primary_thumb_path
    out["sku_thumb_path"] = primary
    out["sku_thumb_url"] = _path_to_url(primary) if primary else None
    for img in out["images"]:
        img["src_url"] = _path_to_url(img.get("src_path"))
        img["master_urls"] = {
            k: _path_to_url(v) for k, v in (img.get("master_paths") or {}).items()
        }
        # 历史版本：dict[ratio, list[{path, url}]]，新→旧，list[0] = primary
        hist_raw = img.get("master_history") or {}
        # 兜底：history 为空但 master_paths 有 → 自动用 primary 作单元素历史
        if not hist_raw and (img.get("master_paths") or {}):
            hist_raw = {k: [v] for k, v in (img["master_paths"] or {}).items() if v}
        img["master_history_urls"] = {
            k: [{"path": p, "url": _path_to_url(p) or ""} for p in (paths_list or [])]
            for k, paths_list in hist_raw.items()
        }
        img["derived_urls"] = {
            k: _path_to_url(v) for k, v in (img.get("derived_paths") or {}).items()
        }
    # 注入每张原图的"排队中的 ratio 集合"（让前端只对这几格显示生成中）
    from img2ec.infra import state_store
    for img in out["images"]:
        img["pending_ratios"] = sorted(state_store.pending_ratios_get(img["id"]))
    # 尺寸图：扫所有 (style, image_idx) 组合；状态从 Redis 跨进程读
    dim_urls: dict[str, str] = {}
    state = state_store.dim_get_all(variant.id)
    dim_states: dict[str, dict] = {}
    for style in DIMENSION_STYLES:
        for idx in range(len(variant.images)):
            key = f"{style}_img{idx}"
            p = _dimension_image_path_for_variant(variant, style, idx)
            if p is not None and p.exists():
                url = _path_to_url(str(p))
                if url:
                    dim_urls[key] = url
            # state per combo
            dim_states[key] = {
                "status": state.get(key, {}).get("status", "idle"),
                "err": state.get(key, {}).get("err"),
            }
        # 兼容字段：style 单写（指向 img0）
        single_key_url = dim_urls.get(f"{style}_img0")
        if single_key_url:
            dim_urls[style] = single_key_url
        dim_states[style] = dim_states.get(f"{style}_img0", {"status": "idle", "err": None})
    out["dimension_urls"] = dim_urls
    out["dimension_states"] = dim_states
    return out


def _enrich(sku: SKU) -> dict:
    """Serialize SKU + variants + 兼容字段（聚合 default variant 数据）。"""
    out = SKUOut.model_validate(sku).model_dump()
    # variants 列表（顺序：default 在前）
    out["variants"] = [_enrich_variant(v) for v in sku.variants]
    # images 兼容：聚合所有变体的图（前端可由 variants[].images 拆出，但保留聚合避免老代码炸）
    all_images: list[dict] = []
    for v_out in out["variants"]:
        all_images.extend(v_out["images"])
    out["images"] = all_images
    # 兼容字段：dimension_urls/states 取 default variant 的（前端老路径还在用）
    default_v = out["variants"][0] if out["variants"] else None
    out["dimension_urls"] = default_v["dimension_urls"] if default_v else {}
    out["dimension_states"] = default_v["dimension_states"] if default_v else {}
    return out


def _get_variant_or_default(sku: SKU, variant_id: str | None):
    """根据可选 variant_id 取 variant；未指定时返回 default。"""
    if variant_id is None:
        return sku.default_variant
    for v in sku.variants:
        if v.id == variant_id:
            return v
    return None


# 兼容旧调用：保留 _dimension_image_path 名字，但内部走 variant 版（用 default variant）
def _dimension_image_path(sku: SKU, style: str = "white") -> Path | None:
    return _dimension_image_path_for_variant(sku.default_variant, style)


@router.get("", response_model=list[SKUOut])
def list_skus(project_id: str, db: Session = Depends(get_session)) -> list[dict]:
    rows = db.query(SKU).filter_by(project_id=project_id).all()
    return [_enrich(s) for s in rows]


@router.post("", response_model=SKUOut, status_code=201)
def create_sku(project_id: str, payload: SKUCreate, db: Session = Depends(get_session)) -> dict:
    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(404, "project not found")
    # 同项目内 SKU 名称唯一（避免共享磁盘目录导致资产串）
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "SKU 名称不能为空")
    existing = db.query(SKU).filter_by(project_id=project_id, name=name).first()
    if existing:
        raise HTTPException(
            409,
            f"项目内已存在同名 SKU「{name}」(id={existing.id[:8]}…)。"
            f"请换个名字，或先删除老的。同名会共享磁盘目录导致老资产污染新 SKU。",
        )
    sku = SKU(id=str(uuid.uuid4()), project_id=project_id, name=name,
              scene_id=payload.scene_id, status=SKUStatus.DRAFT.value)
    db.add(sku)
    # 自动建默认变体；多色场景 Phase 4 加变体 CRUD
    db.add(Variant(
        id=str(uuid.uuid4()), product_id=sku.id, color_name="默认", status="draft",
    ))

    skud = sku_dir(Path(proj.root_path).parent, proj.name, payload.name, sku.id)
    ensure_sku_dirs(skud)

    db.commit()
    db.refresh(sku)
    return _enrich(sku)


@router.get("/{sku_id}", response_model=SKUOut)
def get_sku(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> dict:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    return _enrich(sku)


@router.delete("/{sku_id}", status_code=204)
def delete_sku(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> None:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    # 删 DB 前先记下磁盘路径，删 DB 后清盘上文件（避免同名 SKU 复活时捡到孤儿资产）
    proj = sku.project
    sku_path = None
    if proj is not None:
        try:
            sku_path = sku_dir(Path(proj.root_path).parent, proj.name, sku.name, sku.id)
        except Exception:
            sku_path = None
    db.delete(sku)
    db.commit()
    if sku_path and sku_path.exists():
        import shutil
        try:
            shutil.rmtree(sku_path)
        except OSError:
            pass  # 文件没了不是错


@router.post("/{sku_id}/images", response_model=SKUOut, status_code=201)
def upload_image(
    project_id: str, sku_id: str,
    file: UploadFile = File(...),
    variant_id: str | None = None,
    db: Session = Depends(get_session),
) -> SKU:
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    proj = db.get(Project, project_id)

    variant = _get_variant_or_default(sku, variant_id)
    if variant is None:
        variant = Variant(
            id=str(uuid.uuid4()), product_id=sku.id, color_name="默认", status="draft",
        )
        db.add(variant)
        db.flush()

    from img2ec.infra.fs_layout import variant_dir as variant_dir_fn
    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name, sku.id)
    vdir = variant_dir_fn(skud, variant)
    src_d = vdir / "source"
    src_d.mkdir(parents=True, exist_ok=True)

    orig_name = file.filename or "upload"
    raw_bytes = file.file.read()
    # HEIC 自动转 JPG — Codex 拒绝 heic 输入；同时让前端 <img> 也能直显
    final_name = orig_name
    if orig_name.lower().endswith((".heic", ".heif")):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
            from PIL import Image
            import io
            with Image.open(io.BytesIO(raw_bytes)) as im:
                rgb = im.convert("RGB")
                buf = io.BytesIO()
                rgb.save(buf, "JPEG", quality=92)
                raw_bytes = buf.getvalue()
            final_name = Path(orig_name).with_suffix(".jpg").name
        except Exception as e:
            raise HTTPException(400, f"HEIC 解码失败：{e}")
    dst = src_d / final_name
    dst.write_bytes(raw_bytes)

    img = SourceImage(
        id=str(uuid.uuid4()), variant_id=variant.id, name=final_name, src_path=str(dst),
        status=ImageStatus.READY.value,
    )
    db.add(img)
    if sku.status == SKUStatus.DRAFT.value:
        sku.status = SKUStatus.READY.value
    db.commit()
    db.refresh(sku)
    return _enrich(sku)


@router.delete("/{sku_id}/images/{image_id}", status_code=204)
def delete_image(project_id: str, sku_id: str, image_id: str, db: Session = Depends(get_session)) -> None:
    img = db.get(SourceImage, image_id)
    if img is None or img.sku_id != sku_id:
        raise HTTPException(404, "image not found")
    if img.status in (ImageStatus.CUTTING.value, ImageStatus.GENERATING.value, ImageStatus.COMPOSING.value):
        raise HTTPException(409, "cannot delete an image while it is being processed; stop first")
    Path(img.src_path).unlink(missing_ok=True)
    db.delete(img)
    db.commit()


class SkuPatchRequest(BaseModel):
    scene_id: str | None = None           # 传 string → 切换；不传 → 不改
    clear_scene: bool = False             # true → 把 scene_id 显式置 null（"不选任何模板"）
    name: str | None = None               # 改 SKU 名（同项目唯一；会重命名磁盘目录）


@router.patch("/{sku_id}", response_model=SKUOut)
def patch_sku(
    project_id: str, sku_id: str,
    payload: SkuPatchRequest,
    db: Session = Depends(get_session),
) -> dict:
    """更新 SKU 字段：name / scene_id / clear_scene。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")

    # 1) 改名 + 重命名磁盘目录 + DB 路径同步
    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(400, "SKU 名称不能为空")
        if new_name != sku.name:
            existing = db.query(SKU).filter_by(project_id=project_id, name=new_name).first()
            if existing and existing.id != sku.id:
                raise HTTPException(409, f"项目内已存在同名 SKU「{new_name}」")
            proj = sku.project
            if proj:
                from img2ec.infra.fs_layout import slug as fs_slug
                root = Path(proj.root_path).parent
                old_dir = root / fs_slug(proj.name) / f"{fs_slug(sku.name)}-{sku.id[:8]}"
                new_dir = root / fs_slug(proj.name) / f"{fs_slug(new_name)}-{sku.id[:8]}"
                if old_dir.exists() and not new_dir.exists():
                    old_dir.rename(new_dir)
                old_str, new_str = str(old_dir), str(new_dir)

                def fix(s: str | None) -> str | None:
                    if not s: return s
                    if s.startswith(old_str + "/"): return new_str + s[len(old_str):]
                    if s == old_str: return new_str
                    return s

                for v in sku.variants:
                    if v.sku_thumb_path:
                        v.sku_thumb_path = fix(v.sku_thumb_path)
                    if v.sku_thumb_paths:
                        v.sku_thumb_paths = [fix(p) for p in v.sku_thumb_paths]
                    for im in v.images:
                        im.src_path = fix(im.src_path) or im.src_path
                        if im.master_paths:
                            im.master_paths = {k: fix(v) for k, v in im.master_paths.items()}
                        if im.master_history:
                            im.master_history = {k: [fix(p) for p in lst] for k, lst in im.master_history.items()}
                        if im.derived_paths:
                            im.derived_paths = {k: fix(v) for k, v in im.derived_paths.items()}
            sku.name = new_name

    # 2) 模板：scene_id 改 OR 显式清除
    if payload.clear_scene:
        sku.scene_id = None
    elif payload.scene_id is not None:
        from img2ec.models import Scene
        sc = db.get(Scene, payload.scene_id)
        if sc is None or sc.project_id != project_id:
            raise HTTPException(404, "scene not found in this project")
        sku.scene_id = payload.scene_id

    db.commit()
    db.refresh(sku)
    return _enrich(sku)


class ImagePatchRequest(BaseModel):
    scene_id: str | None = None  # null = 清除 per-image override，走 SKU 默认


@router.patch("/{sku_id}/images/{image_id}", response_model=SKUOut)
def patch_image(
    project_id: str, sku_id: str, image_id: str,
    payload: ImagePatchRequest,
    db: Session = Depends(get_session),
) -> dict:
    """改单图的 scene_id（per-image 模板覆盖）。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    img = db.get(SourceImage, image_id)
    if img is None or img.sku_id != sku_id:
        raise HTTPException(404, "image not found")
    if payload.scene_id is not None:
        from img2ec.models import Scene
        sc = db.get(Scene, payload.scene_id)
        if sc is None or sc.project_id != project_id:
            raise HTTPException(404, "scene not found in this project")
    img.scene_id = payload.scene_id
    db.commit()
    db.refresh(sku)
    return _enrich(sku)


VALID_RATIOS = {"1x1", "long", "3x4", "9x16", "16x9", "front", "side", "detail"}
ORDERED_RATIOS = ["1x1", "long", "3x4", "9x16", "16x9", "front", "side", "detail"]


@router.get("/{sku_id}/preview-prompt")
def preview_prompt(
    project_id: str, sku_id: str,
    extra_prompt: str = "",
    extra_weight: float = 0.0,
    extra_negative_prompt: str = "",
    disable_scene: bool = False,
    db: Session = Depends(get_session),
) -> dict:
    """返回该 SKU 当前 scene 拼装出的 5 个 ratio 完整 prompt（前端展示用）。
    disable_scene=true → 模拟"启用模板"关闭：preview 与实际 codex 提交完全一致。
    """
    from img2ec.infra.codex_image import build_master_prompt
    from img2ec.models import Scene

    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    scene = db.get(Scene, sku.scene_id) if sku.scene_id else None
    # disable_scene 或无 scene → 全部 scene 信息清空，纯人工 prompt 模式
    effective_scene = scene if not disable_scene else None
    sp = effective_scene.prompt if effective_scene else ""
    return {
        "scene_name": effective_scene.name if effective_scene else "",
        "scene_prompt": sp,
        "negative_prompt": effective_scene.negative_prompt if effective_scene else "",
        "per_ratio": {
            r: build_master_prompt(
                scene_prompt=sp, ratio_key=r,
                extra_prompt=extra_prompt, extra_weight=extra_weight,
                extra_negative_prompt=extra_negative_prompt,
            )
            for r in ORDERED_RATIOS
        },
    }


class ProcessRequest(BaseModel):
    ratios: list[str] | None = None  # None=全部 5 个；指定 ⊂ {"1x1","long","3x4","9x16","16x9"}
    extra_prompt: str = ""
    extra_negative_prompt: str = ""  # 用户人工负面提示词；不持久化，仅本次生成
    extra_weight: float = 0.0
    image_ids: list[str] | None = None  # 仅处理这些 image；None = 整个 variant 的所有图
    overwrite: bool = False           # true → 覆盖原版本（不开 v2/v3）
    disable_scene: bool = False       # true → 本次生成不用 SKU 模板（不动 DB）


@router.post("/{sku_id}/process", status_code=202)
def process_sku(
    project_id: str, sku_id: str,
    payload: ProcessRequest | None = None,
    variant_id: str | None = None,
    db: Session = Depends(get_session),
) -> dict:
    """触发生成。
    - image_ids 指定：只处理这些图（跨 variant）
    - 否则按 variant_id 处理（None = 所有 variant）
    - ratios：未指定即全部 8 种规格
    """
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    ratios = payload.ratios if payload else None
    extra_prompt = (payload.extra_prompt if payload else "") or ""
    extra_negative_prompt = (payload.extra_negative_prompt if payload else "") or ""
    extra_weight = float(payload.extra_weight if payload else 0.0)
    disable_scene = bool(payload.disable_scene if payload else False)
    overwrite = bool(payload.overwrite if payload else False)
    # 关闭模板 OR SKU 没模板 → 必须有 extra_prompt 兜底
    effective_no_scene = disable_scene or sku.scene_id is None
    if effective_no_scene and not extra_prompt.strip():
        any_img_has_scene = (not disable_scene) and any(
            im.scene_id for v in sku.variants for im in v.images
        )
        if not any_img_has_scene:
            raise HTTPException(400, "未启用模板且未填提示词；至少二选一")
    image_ids_filter = (payload.image_ids if payload else None) or None
    if ratios is not None:
        if not ratios:
            raise HTTPException(400, "ratios cannot be empty list (omit field for all 8)")
        invalid = set(ratios) - VALID_RATIOS
        if invalid:
            raise HTTPException(400, f"invalid ratios: {sorted(invalid)}")
        wanted = sorted(ratios)
    else:
        wanted = sorted(VALID_RATIOS)

    if variant_id is not None:
        target_variants = [v for v in sku.variants if v.id == variant_id]
        if not target_variants:
            raise HTTPException(404, "variant not found")
    else:
        target_variants = list(sku.variants)

    if not any(v.images for v in target_variants):
        raise HTTPException(400, "no source images on SKU")

    # 全部入队：worker pool 按 concurrency 调度，无需"跳过 in-flight"
    IN_FLIGHT = {
        ImageStatus.PENDING.value, ImageStatus.CUTTING.value,
        ImageStatus.GENERATING.value, ImageStatus.COMPOSING.value,
    }
    sku.status = SKUStatus.RUNNING.value
    image_ids: list[str] = []
    fresh_image_ids: list[str] = []  # 此次重新激活的图（之前 done/failed/draft）
    filter_set = set(image_ids_filter) if image_ids_filter else None
    for v in target_variants:
        for img in v.images:
            if filter_set is not None and img.id not in filter_set:
                continue
            if img.status not in IN_FLIGHT:
                fresh_image_ids.append(img.id)
                img.status = ImageStatus.PENDING.value
                img.err_msg = None
            image_ids.append(img.id)
    if filter_set is not None and not image_ids:
        raise HTTPException(400, "image_ids 中没有匹配该 SKU 的图")
    db.commit()

    from img2ec.infra import state_store
    from img2ec.tasks.pipeline_tasks import process_image_task
    # 自愈：fresh 图清掉孤儿 pending_ratios（上次入队失败留下的）
    for iid in fresh_image_ids:
        state_store.pending_ratios_clear(iid)
    # 先发 celery 任务（失败抛错），成功后才记录 pending，避免 Redis 孤儿
    for iid in image_ids:
        process_image_task.delay(iid, wanted, extra_prompt, extra_weight, extra_negative_prompt, overwrite, disable_scene)
        state_store.pending_ratios_add(iid, wanted)

    return {"queued": len(image_ids), "ratios": wanted}


@router.post("/{sku_id}/cancel", status_code=200)
def cancel_sku(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> dict:
    """请求停止处理。Pipeline 会在下一个 master 完成后检测到并 bail；已生成的 master 保留。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    if sku.status != SKUStatus.RUNNING.value:
        raise HTTPException(400, f"only running SKU can be cancelled (current: {sku.status})")
    sku.status = "cancelled"
    db.commit()
    return {"ok": True}


class DeleteMasterVersionRequest(BaseModel):
    image_id: str
    ratio: str
    path: str  # 绝对路径（前端从 master_history_urls 取的 path 字段回传）


@router.post("/{sku_id}/master-versions/delete", status_code=200)
def delete_master_version(
    project_id: str, sku_id: str,
    payload: DeleteMasterVersionRequest,
    db: Session = Depends(get_session),
) -> dict:
    """删除某张 master 图的一个版本。如删的是 primary，下一个版本自动升 primary。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")

    from img2ec.models import SourceImage
    img = db.get(SourceImage, payload.image_id)
    if img is None:
        raise HTTPException(404, "image not found")

    hist = {k: list(v) for k, v in (img.master_history or {}).items()}
    # 兜底：旧数据没 history 但 master_paths 里有
    mp = dict(img.master_paths or {})
    if payload.ratio not in hist and payload.ratio in mp:
        hist[payload.ratio] = [mp[payload.ratio]]

    versions = hist.get(payload.ratio, [])
    if payload.path not in versions:
        raise HTTPException(404, "version not found for this ratio")

    versions = [p for p in versions if p != payload.path]
    # 物理文件
    try:
        Path(payload.path).unlink()
    except FileNotFoundError:
        pass

    if versions:
        hist[payload.ratio] = versions
        mp[payload.ratio] = versions[0]  # primary = newest 余下
    else:
        hist.pop(payload.ratio, None)
        mp.pop(payload.ratio, None)
        # 派生图按 ratio 找不到 primary 后无法更新，留旧的（用户可重生）

    img.master_history = hist
    img.master_paths = mp
    db.commit()
    db.refresh(sku)
    return _enrich(sku)


class ApplyDimensionRequest(BaseModel):
    style: str = "white"  # "white" | "template"


class DetailComposeRequest(BaseModel):
    image_keys: list[str]  # 顺序敏感：master ratio (1x1/long/...) 或 size_white/size_template


@router.post("/{sku_id}/variants/{variant_id}/detail/compose", response_model=SKUOut, status_code=200)
def compose_detail_page(
    project_id: str, sku_id: str, variant_id: str,
    payload: DetailComposeRequest,
    db: Session = Depends(get_session),
) -> dict:
    """用用户选定的 image_keys 顺序重渲该变体在 3 平台的详情页。

    第一个 image_key 作为 hero（建议 1x1）；其余按顺序作为 full_image 或 size_diagram module。
    标题/卖点段始终保留（来自该变体的 PlatformOutputCopy）。
    """
    from img2ec.core.detail_page import render_detail_page
    from img2ec.core.detail_template import DEFAULT_TEMPLATE
    from img2ec.infra.fs_layout import variant_detail_path
    from img2ec.models import PlatformOutputCopy, Variant

    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    primary = db.get(Variant, variant_id)
    if primary is None or primary.product_id != sku.id:
        raise HTTPException(404, "variant not found")
    if not primary.images:
        raise HTTPException(400, "no images in variant")
    if not payload.image_keys:
        raise HTTPException(400, "image_keys cannot be empty")

    images_dict: dict[str, Path] = {}
    modules_after_selling: list[dict] = []
    hero_key: str | None = None

    def _resolve(k: str) -> Path | None:
        """ratio key 解析：'img<idx>:<ratio>' / 'size_<style>[_img<N>]' / 旧 '<ratio>'（→ img0）"""
        if k.startswith("size_"):
            import re as _re
            rest = k[len("size_"):]
            m = _re.match(r"^(white|template)(?:_img(\d+))?$", rest)
            if not m:
                return None
            style = m.group(1)
            idx = int(m.group(2)) if m.group(2) is not None else 0
            p = _dimension_image_path_for_variant(primary, style, idx)
            return p if p and p.exists() else None
        if k.startswith("img"):
            import re
            m = re.match(r"img(\d+):(.+)", k)
            if not m:
                return None
            idx = int(m.group(1)); ratio = m.group(2)
            if idx >= len(primary.images):
                return None
            mp = primary.images[idx].master_paths or {}
            return Path(mp[ratio]) if ratio in mp else None
        # legacy: bind to img0
        mp = primary.images[0].master_paths or {} if primary.images else {}
        return Path(mp[k]) if k in mp else None

    for i, k in enumerate(payload.image_keys):
        path = _resolve(k)
        if path is None:
            continue
        images_dict[k] = path
        if k.startswith("size_"):
            modules_after_selling.append({"type": "size_diagram", "config": {"key": k, "title": "商品尺寸"}})
            continue
        # hero 优先：第一张以 1x1 结尾的当 hero；否则第一个非 size 的当 hero
        is_one_by_one = k == "1x1" or k.endswith(":1x1")
        if hero_key is None and is_one_by_one:
            hero_key = k
            # 同时绑定到 "1x1" key（hero module 看的 key）
            images_dict["1x1"] = path
            continue
        if i == 0 and hero_key is None:
            hero_key = k
            images_dict["1x1"] = path
            continue
        modules_after_selling.append({"type": "full_image", "config": {"_key": k}})

    if hero_key is None or "1x1" not in images_dict:
        raise HTTPException(400, "compose requires at least one 1x1 master in image_keys")

    # 多变体颜色对比块（自动）
    variants_meta = []
    if len(sku.variants) > 1:
        for v in sku.variants:
            v_img = v.images[0] if v.images else None
            m = (v_img.master_paths or {}).get("1x1") if v_img else None
            if m:
                variants_meta.append({"color_name": v.color_name, "image_path": Path(m)})

    modules = [
        {"type": "hero", "config": {"height": 750, "scale": 0.78, "bg_color": [248, 244, 238]}},
        {"type": "title_banner", "config": {"height": 280, "title_size": 40, "subtitle_size": 22}},
        {"type": "selling_points", "config": {"max_points": 3, "accent_color": [191, 130, 60]}},
    ]
    if len(variants_meta) >= 2:
        modules.append({"type": "color_comparison", "config": {}})
    modules.extend(modules_after_selling)

    template = {"canvas_width": DEFAULT_TEMPLATE["canvas_width"], "modules": modules}

    proj = sku.project
    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name, sku.id)
    copies = db.query(PlatformOutputCopy).filter_by(variant_id=primary.id).all()
    if not copies:
        raise HTTPException(400, "no copy generated yet for this variant — wait then retry")

    for c in copies:
        copy_dict = {
            "title": c.title, "subtitle": c.subtitle,
            "selling_points": c.selling_points or [],
        }
        out_path = variant_detail_path(skud, primary, c.platform)
        render_detail_page(
            template=template, copy=copy_dict, images=images_dict,
            output_path=out_path, variants=variants_meta,
        )

    db.refresh(sku)
    return _enrich(sku)


@router.post("/{sku_id}/variants/{variant_id}/dimension/apply-to-detail", response_model=SKUOut, status_code=200)
def apply_dimension_to_detail(
    project_id: str, sku_id: str, variant_id: str,
    payload: ApplyDimensionRequest | None = None,
    db: Session = Depends(get_session),
) -> dict:
    """把指定 style 的尺寸图作为 module 加入该变体的详情页底部并重渲 3 平台。"""
    from img2ec.core.detail_page import render_detail_page
    from img2ec.core.detail_template import DEFAULT_TEMPLATE
    from img2ec.infra.fs_layout import variant_detail_path
    from img2ec.models import PlatformOutputCopy, Variant

    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    primary = db.get(Variant, variant_id)
    if primary is None or primary.product_id != sku.id:
        raise HTTPException(404, "variant not found")
    if not primary.images:
        raise HTTPException(400, "no source images in variant")

    style = (payload.style if payload else "white") or "white"
    if style not in DIMENSION_STYLES:
        raise HTTPException(400, f"invalid style: {style}; allowed: {list(DIMENSION_STYLES)}")

    chosen_path = _dimension_image_path_for_variant(primary, style, 0)
    if chosen_path is None or not chosen_path.exists():
        raise HTTPException(400, f"dimension diagram for style={style} not generated yet")

    img = primary.images[0]
    master_paths = {k: Path(v) for k, v in (img.master_paths or {}).items()}
    images_dict = {**master_paths, f"size_{style}": chosen_path}
    if "1x1" not in images_dict:
        raise HTTPException(400, "1x1 master required for detail page")

    # 多变体颜色对比
    variants_meta = []
    if len(sku.variants) > 1:
        for v in sku.variants:
            v_img = v.images[0] if v.images else None
            m = (v_img.master_paths or {}).get("1x1") if v_img else None
            if m:
                variants_meta.append({"color_name": v.color_name, "image_path": Path(m)})

    modules = list(DEFAULT_TEMPLATE["modules"])
    if len(variants_meta) >= 2:
        new_mods = []
        for m in modules:
            new_mods.append(m)
            if m.get("type") == "selling_points":
                new_mods.append({"type": "color_comparison", "config": {}})
        modules = new_mods
    modules.append({"type": "size_diagram", "config": {"key": f"size_{style}", "title": "商品尺寸"}})

    template = {**DEFAULT_TEMPLATE, "modules": modules}

    proj = sku.project
    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name, sku.id)

    copies = db.query(PlatformOutputCopy).filter_by(variant_id=primary.id).all()
    if not copies:
        raise HTTPException(400, "no copy generated yet for this variant — wait then retry")

    for c in copies:
        copy_dict = {
            "title": c.title, "subtitle": c.subtitle,
            "selling_points": c.selling_points or [],
        }
        out_path = variant_detail_path(skud, primary, c.platform)
        render_detail_page(
            template=template, copy=copy_dict, images=images_dict,
            output_path=out_path, variants=variants_meta,
        )

    db.refresh(sku)
    return _enrich(sku)


@router.patch("/{sku_id}/dimensions", response_model=SKUOut)
def update_dimensions(
    project_id: str, sku_id: str,
    payload: SKUDimensions,
    db: Session = Depends(get_session),
) -> dict:
    """更新 SKU 物理尺寸（cm）。三项可分别为空。改尺寸后前端可单独触发 regenerate。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    sku.length_cm = payload.length_cm
    sku.width_cm = payload.width_cm
    sku.height_cm = payload.height_cm
    db.commit()
    db.refresh(sku)
    return _enrich(sku)


class RegenerateImageRequest(BaseModel):
    ratios: list[str] | None = None  # None=全 8 比例
    extra_prompt: str = ""
    extra_negative_prompt: str = ""
    extra_weight: float = 0.0


@router.post("/{sku_id}/images/{image_id}/regenerate", status_code=202)
def regenerate_single_image(
    project_id: str, sku_id: str, image_id: str,
    payload: RegenerateImageRequest | None = None,
    db: Session = Depends(get_session),
) -> dict:
    """重新生成某张原图的全部规格（默认 8 比例，可指定 ratios 子集）。
    跳过该图当前 in-flight 状态（避免重复入队）。"""
    from img2ec.models import SourceImage
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    img = db.get(SourceImage, image_id)
    if img is None:
        raise HTTPException(404, "image not found")

    extra_prompt = (payload.extra_prompt if payload else "") or ""
    extra_negative_prompt = (payload.extra_negative_prompt if payload else "") or ""
    extra_weight = float(payload.extra_weight if payload else 0.0)
    effective_scene_id = img.scene_id or sku.scene_id
    if effective_scene_id is None and not extra_prompt.strip():
        raise HTTPException(400, "未选模板且未填提示词；至少二选一")

    ratios = (payload.ratios if payload else None) or sorted(VALID_RATIOS)
    invalid = set(ratios) - VALID_RATIOS
    if invalid:
        raise HTTPException(400, f"invalid ratios: {sorted(invalid)}")

    # 不再 skip in-flight：直接 enqueue。Celery worker pool 自动调度（concurrency 个并发）。
    IN_FLIGHT = {ImageStatus.PENDING.value, ImageStatus.CUTTING.value,
                 ImageStatus.GENERATING.value, ImageStatus.COMPOSING.value}
    if img.status not in IN_FLIGHT:
        img.status = ImageStatus.PENDING.value
        img.err_msg = None
    sku.status = SKUStatus.RUNNING.value
    db.commit()

    from img2ec.infra import state_store
    state_store.pending_ratios_add(image_id, sorted(ratios))
    from img2ec.tasks.pipeline_tasks import process_image_task
    process_image_task.delay(image_id, sorted(ratios), extra_prompt, extra_weight, extra_negative_prompt)
    return {"queued": 1, "image_id": image_id, "ratios": sorted(ratios)}


@router.post("/{sku_id}/images/{image_id}/delete-all-masters", response_model=SKUOut)
def delete_all_masters_for_image(
    project_id: str, sku_id: str, image_id: str,
    db: Session = Depends(get_session),
) -> dict:
    """删除该原图下所有 master 版本（含历史 + primary）。物理文件 + DB 一并清。"""
    from img2ec.models import SourceImage
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    img = db.get(SourceImage, image_id)
    if img is None:
        raise HTTPException(404, "image not found")

    # 收集所有要删的路径（master_history 优先，fallback 到 master_paths）
    all_paths: set[str] = set()
    for k, lst in (img.master_history or {}).items():
        for p in lst:
            if p: all_paths.add(p)
    for k, p in (img.master_paths or {}).items():
        if p: all_paths.add(p)
    for p in all_paths:
        try: Path(p).unlink()
        except FileNotFoundError: pass
        except OSError: pass

    img.master_history = {}
    img.master_paths = {}
    # 派生图也清（基于已删的 master）
    img.derived_paths = {}
    db.commit()
    db.refresh(sku)
    return _enrich(sku)


class DimensionDeleteRequest(BaseModel):
    variant_id: str
    style: str  # white | template
    image_idx: int


@router.post("/{sku_id}/dimension/delete-all", response_model=SKUOut)
def delete_all_dimension(
    project_id: str, sku_id: str,
    variant_id: str | None = None,
    db: Session = Depends(get_session),
) -> dict:
    """删除该变体（缺省 default）下所有尺寸图文件 + Redis 状态。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    variant = _get_variant_or_default(sku, variant_id)
    if variant is None:
        raise HTTPException(404, "variant not found")

    from img2ec.infra import state_store
    for style in DIMENSION_STYLES:
        for i in range(len(variant.images)):
            p = _dimension_image_path_for_variant(variant, style, i)
            if p and p.exists():
                try: p.unlink()
                except OSError: pass
            state_store.dim_clear(variant.id, f"{style}_img{i}")

    db.refresh(sku)
    return _enrich(sku)


@router.post("/{sku_id}/dimension/delete", status_code=200)
def delete_dimension_image(
    project_id: str, sku_id: str,
    payload: DimensionDeleteRequest,
    db: Session = Depends(get_session),
) -> dict:
    """删除某张尺寸图（单张 = style × image_idx）。物理文件 + 状态都清。"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    variant = next((v for v in sku.variants if v.id == payload.variant_id), None)
    if variant is None:
        raise HTTPException(404, "variant not found")
    if payload.style not in DIMENSION_STYLES:
        raise HTTPException(400, f"invalid style {payload.style}")
    if payload.image_idx < 0 or payload.image_idx >= len(variant.images):
        raise HTTPException(400, "image_idx out of range")

    p = _dimension_image_path_for_variant(variant, payload.style, payload.image_idx)
    if p is not None and p.exists():
        try:
            p.unlink()
        except OSError as e:
            raise HTTPException(500, f"failed to delete file: {e}")

    # 清状态
    from img2ec.infra import state_store
    state_store.dim_clear(variant.id, f"{payload.style}_img{payload.image_idx}")

    db.refresh(sku)
    return _enrich(sku)


class DimensionRegenerateRequest(BaseModel):
    styles: list[str] = ["white"]  # subset of {"white","template"}
    image_indices: list[int] | None = None  # 哪些原图（按 variant.images 索引）；None=只用第 0 张


@router.post("/{sku_id}/dimension/regenerate", response_model=SKUOut, status_code=202)
def regenerate_dimension_diagram(
    project_id: str, sku_id: str,
    payload: DimensionRegenerateRequest | None = None,
    variant_id: str | None = None,
    db: Session = Depends(get_session),
) -> dict:
    """异步为指定变体（缺省 default）生成尺寸图。"""
    from img2ec.models import Scene

    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    if sku.length_cm is None or sku.width_cm is None or sku.height_cm is None:
        raise HTTPException(400, "all three dimensions (length/width/height) must be set")

    variant = _get_variant_or_default(sku, variant_id)
    if variant is None or not variant.images:
        raise HTTPException(400, "variant has no source images")

    requested = (payload.styles if payload else None) or ["white"]
    invalid = [s for s in requested if s not in DIMENSION_STYLES]
    if invalid:
        raise HTTPException(400, f"invalid styles: {invalid}; allowed: {list(DIMENSION_STYLES)}")
    if not requested:
        raise HTTPException(400, "styles cannot be empty")

    indices = (payload.image_indices if payload and payload.image_indices is not None else [0])
    bad_idx = [i for i in indices if i < 0 or i >= len(variant.images)]
    if bad_idx:
        raise HTTPException(400, f"image_indices out of range: {bad_idx}")
    if not indices:
        raise HTTPException(400, "image_indices cannot be empty")

    scene = db.get(Scene, sku.scene_id) if sku.scene_id else None
    if "template" in requested and (scene is None or not scene.prompt):
        raise HTTPException(400, "template style requires SKU to have a scene template assigned")

    # (style, idx) 组合 — 状态通过 Redis 跨进程共享
    from img2ec.infra import state_store
    combos = [(s, i) for s in requested for i in indices]
    existing = state_store.dim_get_all(variant.id)
    busy_combos = [f"{s}_img{i}" for s, i in combos if existing.get(f"{s}_img{i}", {}).get("status") == "generating"]
    if busy_combos:
        raise HTTPException(409, f"already generating: {busy_combos}")

    # 标记 generating + 立即派工到 celery worker
    from img2ec.tasks.dim_tasks import regenerate_dimension_task
    for s, i in combos:
        state_store.dim_set(variant.id, f"{s}_img{i}", "generating")
        regenerate_dimension_task.delay(sku.id, variant.id, s, i)

    db.refresh(sku)
    return _enrich(sku)
