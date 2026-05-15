from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.models import SKU, SKUStatus, ImageStatus
from img2ec.api.skus._helpers import ORDERED_RATIOS, VALID_RATIOS

router = APIRouter()


@router.get("/{sku_id}/preview-prompt")
def preview_prompt(
    project_id: str, sku_id: str,
    extra_prompt: str = "",
    extra_weight: float = 0.0,
    extra_negative_prompt: str = "",
    disable_scene: bool = False,
    has_reference: bool = False,
    variant_id: str | None = None,
    db: Session = Depends(get_session),
) -> dict:
    """返回该 SKU 当前 scene 拼装出的 ratio 完整 prompt（前端展示用）。
    - variant_id：传则取该变体的 scene（变体覆盖 > SKU 默认）；不传走 SKU 默认
    - disable_scene=true → 模拟"启用模板"关闭：纯人工 prompt 模式
    - has_reference=true → 参考图驱动模式（scene 强制忽略；模板/参考图二选一）
    preview 与实际 codex 提交走同一个 build_master_prompt，保证一致。
    """
    from img2ec.infra.codex_image import build_master_prompt
    from img2ec.models import Scene, Variant

    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    effective_scene_id: str | None = sku.scene_id
    if variant_id is not None:
        v = db.get(Variant, variant_id)
        if v is None or v.product_id != sku.id:
            raise HTTPException(404, "variant not found")
        effective_scene_id = v.scene_id or sku.scene_id
    scene = db.get(Scene, effective_scene_id) if effective_scene_id else None
    # disable_scene 或参考图模式 → 全部 scene 信息清空
    effective_scene = scene if not (disable_scene or has_reference) else None
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
                has_reference=has_reference,
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
    reference_image_path: str | None = None  # 本次生成的"参考图驱动"模式（与模板二选一）


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
    reference_image_path: str | None = None
    if payload and payload.reference_image_path:
        from img2ec.api.uploads import validate_reference_path
        reference_image_path = str(validate_reference_path(payload.reference_image_path))
        # 参考图模式自动停模板（UI 端二选一，这里再兜底）
        disable_scene = True
    # 关闭模板 OR 目标变体都没模板（变体覆盖 → SKU 默认 → 都 None）→ 必须有 extra_prompt 或 ref
    if variant_id is not None:
        check_variants = [v for v in sku.variants if v.id == variant_id]
    else:
        check_variants = list(sku.variants)
    any_variant_has_scene = any(
        ((v.scene_id or sku.scene_id) is not None) for v in check_variants
    )
    effective_no_scene = disable_scene or not any_variant_has_scene
    if effective_no_scene and not extra_prompt.strip() and not reference_image_path:
        any_img_has_scene = (not disable_scene) and any(
            im.scene_id for v in check_variants for im in v.images
        )
        if not any_img_has_scene:
            raise HTTPException(400, "模板 / 参考图 / 附加提示词 三选一必填")
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
        process_image_task.delay(
            iid, wanted, extra_prompt, extra_weight, extra_negative_prompt,
            overwrite, disable_scene, reference_image_path,
        )
        state_store.pending_ratios_add(iid, wanted)

    return {"queued": len(image_ids), "ratios": wanted}


@router.post("/{sku_id}/cancel", status_code=200)
def cancel_sku(project_id: str, sku_id: str, db: Session = Depends(get_session)) -> dict:
    """请求停止处理。
    - 立刻把所有 PENDING（还在队列里等的）图标 FAILED，清掉 Redis pending_ratios —
      这些 worker 还没启动，不会被覆盖。
    - 已经在跑的（cutting/generating/composing）由 worker 在下个 progress 回调时
      看到 sku.status=cancelled 自行 bail。已生成的 master 保留。
    """
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    if sku.status != SKUStatus.RUNNING.value:
        raise HTTPException(400, f"only running SKU can be cancelled (current: {sku.status})")
    sku.status = "cancelled"

    from img2ec.infra import state_store
    cancelled_pending = 0
    in_flight = 0
    for v in sku.variants:
        for img in v.images:
            if img.status == ImageStatus.PENDING.value:
                img.status = ImageStatus.FAILED.value
                img.err_msg = "cancelled by user"
                state_store.pending_ratios_clear(img.id)
                cancelled_pending += 1
            elif img.status in {
                ImageStatus.CUTTING.value, ImageStatus.GENERATING.value,
                ImageStatus.COMPOSING.value,
            }:
                in_flight += 1
    db.commit()
    return {"ok": True, "cancelled_pending": cancelled_pending, "in_flight": in_flight}


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
    variant_scene = img.variant.scene_id if img.variant else None
    effective_scene_id = img.scene_id or variant_scene or sku.scene_id
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
