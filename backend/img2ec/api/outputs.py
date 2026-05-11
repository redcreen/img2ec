import io
import re
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from img2ec.db import get_session
from img2ec.infra.fs_layout import outputs_dir, platform_dir, sku_dir
from img2ec.models import PlatformOutputCopy, Project, SKU, SKUStatus, Variant

router = APIRouter(prefix="/api", tags=["outputs"])


class BundleRequest(BaseModel):
    platform: str  # douyin / shipinhao / xiaohongshu
    variant_id: str
    main_keys: list[str] = []     # 主图列表 keys
    detail_keys: list[str] = []   # 详情图列表 keys


_RATIO_ZH = {
    "1x1": "1x1", "long": "长图", "3x4": "3x4", "9x16": "9x16", "16x9": "16x9",
    "front": "正面", "side": "侧面", "detail": "细节",
}
_STYLE_ZH = {"white": "白底", "template": "模板"}


def _safe_name(s: str) -> str:
    return re.sub(r"[^\w\-一-鿿.]+", "_", s).strip("_")[:80] or "x"


def _spec_for_key(variant: Variant, key: str) -> str:
    """从 key 推规格中文字符串。多原图时附加 -原图N 后缀。"""
    if key.startswith("size_"):
        m = re.match(r"^(white|template)(?:_img(\d+))?$", key[len("size_"):])
        if not m:
            return _safe_name(key)
        style_zh = _STYLE_ZH.get(m.group(1), m.group(1))
        idx = int(m.group(2)) if m.group(2) is not None else 0
        if len(variant.images) > 1:
            return f"尺寸图{style_zh}-原图{idx+1}"
        return f"尺寸图{style_zh}"
    if key.startswith("img"):
        m = re.match(r"^img(\d+):(.+)$", key)
        if not m:
            return _safe_name(key)
        idx = int(m.group(1)); ratio = m.group(2)
        ratio_zh = _RATIO_ZH.get(ratio, ratio)
        if len(variant.images) > 1:
            return f"原图{idx+1}-{ratio_zh}"
        return ratio_zh
    return _safe_name(key)


def _spec_for_path(variant: Variant, abs_path: Path) -> str:
    """从 sku_thumb_paths 中存的绝对路径反推规格（按文件名匹配 master / dim）。"""
    # 反查 variant.images[*].master_paths
    for i, img in enumerate(variant.images):
        for r, p in (img.master_paths or {}).items():
            if Path(p) == abs_path:
                ratio_zh = _RATIO_ZH.get(r, r)
                return f"原图{i+1}-{ratio_zh}" if len(variant.images) > 1 else ratio_zh
    # 反查 dim 图（按文件名 stem-dimension-style 模式）
    name = abs_path.stem
    m = re.match(r"^(.+)-dimension-(white|template)$", name)
    if m:
        stem = m.group(1)
        style_zh = _STYLE_ZH.get(m.group(2), m.group(2))
        for i, img in enumerate(variant.images):
            if Path(img.name).stem == stem:
                return f"尺寸图{style_zh}-原图{i+1}" if len(variant.images) > 1 else f"尺寸图{style_zh}"
        return f"尺寸图{style_zh}"
    return _safe_name(name)


def _resolve_image_key(variant: Variant, key: str) -> Path | None:
    """同 variants.py / skus.py 的 resolver — 解析 img<idx>:<ratio> / size_<style>[_img<N>]。"""
    if key.startswith("size_"):
        from img2ec.api.skus import _dimension_image_path_for_variant
        m = re.match(r"^(white|template)(?:_img(\d+))?$", key[len("size_"):])
        if not m:
            return None
        style = m.group(1)
        idx = int(m.group(2)) if m.group(2) is not None else 0
        p = _dimension_image_path_for_variant(variant, style, idx)
        return p if p and p.exists() else None
    if key.startswith("img"):
        m = re.match(r"^img(\d+):(.+)$", key)
        if not m:
            return None
        idx = int(m.group(1))
        ratio = m.group(2)
        if idx >= len(variant.images):
            return None
        mp = (variant.images[idx].master_paths or {})
        if ratio not in mp:
            return None
        p = Path(mp[ratio])
        return p if p.exists() else None
    return None


@router.post("/projects/{project_id}/skus/{sku_id}/download-bundle")
def download_bundle(project_id: str, sku_id: str, payload: BundleRequest,
                    db: Session = Depends(get_session)):
    """打包用户选定的资料：主图/ + SKU图/ + 详情图/ + 文案.txt"""
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    variant = db.get(Variant, payload.variant_id)
    if variant is None or variant.product_id != sku.id:
        raise HTTPException(404, "variant not found")
    if payload.platform not in {"douyin", "shipinhao", "xiaohongshu"}:
        raise HTTPException(400, "invalid platform")

    proj = sku.project
    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name)

    buf = io.BytesIO()
    counts = {"main": 0, "sku": 0, "detail": 0}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        _write_main(zf, variant, payload.main_keys, "主图", counts)
        _write_sku(zf, variant, "SKU图", counts)
        _write_detail(zf, variant, payload.detail_keys, skud, payload.platform, "详情图", counts)
        _write_copy(zf, db, sku_id, payload.platform, "文案.txt")

    if sum(counts.values()) == 0:
        raise HTTPException(400, "没有可下载的内容（请先生成 master / 选择主图 / 应用详情页）")

    buf.seek(0)
    fname = _safe_name(f"{sku.name}-{variant.color_name}-{payload.platform}") + ".zip"
    from urllib.parse import quote
    ascii_fb = fname.encode("ascii", "replace").decode("ascii").replace("?", "_")
    cd = f"attachment; filename=\"{ascii_fb}\"; filename*=UTF-8''{quote(fname)}"
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": cd},
    )


def _write_main(zf, variant: Variant, keys: list[str], folder: str, counts: dict) -> None:
    n = 1
    for k in keys:
        p = _resolve_image_key(variant, k)
        if p is None:
            continue
        zf.write(p, arcname=f"{folder}/main-{n}-{_spec_for_key(variant, k)}{p.suffix}")
        n += 1
        counts["main"] += 1


def _write_sku(zf, variant: Variant, folder: str, counts: dict) -> None:
    n = 1
    for p_str in variant.sku_thumb_paths or []:
        p = Path(p_str)
        if not p.exists():
            continue
        zf.write(p, arcname=f"{folder}/sku-{n}-{_spec_for_path(variant, p)}{p.suffix}")
        n += 1
        counts["sku"] += 1


def _write_detail(zf, variant: Variant, keys: list[str], skud: Path,
                  platform: str, folder: str, counts: dict) -> None:
    # 详情图列表里的源图（按用户排序）
    n = 1
    for k in keys:
        p = _resolve_image_key(variant, k)
        if p is None:
            continue
        zf.write(p, arcname=f"{folder}/detail-{n}-{_spec_for_key(variant, k)}{p.suffix}")
        n += 1
        counts["detail"] += 1
    # 合成好的详情页
    dp = platform_dir(skud, platform) / "detail-template.jpg"
    if dp.exists():
        zf.write(dp, arcname=f"{folder}/detail-template.jpg")
        counts["detail"] += 1


def _write_copy(zf, db: Session, sku_id: str, platform: str, name: str) -> None:
    copy_row = db.query(PlatformOutputCopy).filter_by(sku_id=sku_id, platform=platform).first()
    if not copy_row:
        return
    lines = [f"标题：{copy_row.title or ''}"]
    if copy_row.subtitle:
        lines.append(f"副标题：{copy_row.subtitle}")
    if copy_row.selling_points:
        lines.append("\n卖点：")
        for sp in copy_row.selling_points:
            lines.append(f"  · {sp}")
    if copy_row.description_md:
        lines.append("\n描述："); lines.append(copy_row.description_md)
    if copy_row.keywords:
        lines.append("\n关键词：" + ", ".join(copy_row.keywords))
    if copy_row.hashtags:
        lines.append("\n话题标签：" + " ".join(f"#{h.lstrip('#')}" for h in copy_row.hashtags))
    if copy_row.video_script:
        lines.append("\n视频脚本："); lines.append(copy_row.video_script)
    zf.writestr(name, "\n".join(lines).encode("utf-8"))


class BundleAllRequest(BaseModel):
    variant_id: str
    main_keys: list[str] = []
    detail_keys: list[str] = []


PLATFORM_LABELS = {"douyin": "抖店", "shipinhao": "视频号", "xiaohongshu": "小红书"}


@router.post("/projects/{project_id}/skus/{sku_id}/download-bundle-all")
def download_bundle_all(project_id: str, sku_id: str, payload: BundleAllRequest,
                        db: Session = Depends(get_session)):
    """打包用户当前变体的全平台资料。结构：
       主图/        ← 跨平台共用（cur.main）
       SKU图/       ← 跨平台共用（variant.sku_thumb_paths）
       <平台>/详情图/detail-template.jpg
       <平台>/文案.txt
       README.txt
    """
    sku = db.get(SKU, sku_id)
    if sku is None or sku.project_id != project_id:
        raise HTTPException(404, "sku not found")
    variant = db.get(Variant, payload.variant_id)
    if variant is None or variant.product_id != sku.id:
        raise HTTPException(404, "variant not found")

    proj = sku.project
    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name)

    counts = {"main": 0, "sku": 0, "detail": 0}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 主图 / SKU 图：跨平台共用
        _write_main(zf, variant, payload.main_keys, "主图", counts)
        _write_sku(zf, variant, "SKU图", counts)
        # 各平台子目录：详情图列表 + 合成详情图 + 文案
        for platform, zh in PLATFORM_LABELS.items():
            _write_detail(zf, variant, payload.detail_keys, skud, platform, f"{zh}/详情图", counts)
            _write_copy(zf, db, sku_id, platform, f"{zh}/文案.txt")

    if sum(counts.values()) == 0:
        raise HTTPException(400, "没有可下载的内容")

    buf.seek(0)
    fname = _safe_name(f"{sku.name}-{variant.color_name}-全平台") + ".zip"
    from urllib.parse import quote
    # HTTP headers 仅支持 Latin-1；中文用 RFC 5987 编码（filename*=UTF-8''…）
    ascii_fb = fname.encode("ascii", "replace").decode("ascii").replace("?", "_")
    cd = f"attachment; filename=\"{ascii_fb}\"; filename*=UTF-8''{quote(fname)}"
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": cd},
    )


@router.get("/skus/{sku_id}/download")
def download_sku_zip(sku_id: str, db: Session = Depends(get_session)):
    sku = db.get(SKU, sku_id)
    if sku is None:
        raise HTTPException(404, "sku not found")
    proj = db.get(Project, sku.project_id)

    skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name)
    outd = outputs_dir(skud)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in outd.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f.relative_to(outd))
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{sku.name}.zip"'},
    )


@router.get("/projects/{project_id}/download-all")
def download_project_zip(project_id: str, db: Session = Depends(get_session)):
    """打包所有 done 状态 SKU 的 outputs/，每个 SKU 一个目录。"""
    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(404, "project not found")

    done_skus = [s for s in proj.skus if s.status == SKUStatus.DONE.value]
    if not done_skus:
        raise HTTPException(400, "no completed SKUs to download")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for sku in done_skus:
            skud = sku_dir(Path(proj.root_path).parent, proj.name, sku.name)
            outd = outputs_dir(skud)
            if not outd.exists():
                continue
            for f in outd.rglob("*"):
                if f.is_file():
                    arcname = f"{sku.name}/{f.relative_to(outd)}"
                    zf.write(f, arcname=arcname)
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{proj.name}-all.zip"'},
    )
