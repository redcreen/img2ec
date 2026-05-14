import re
from pathlib import Path

VALID_PLATFORMS = {"douyin", "shipinhao", "taobao", "xiaohongshu"}
SLUG_PATTERN = re.compile(r"[^a-zA-Z0-9一-龥_-]+")


def slug(s: str) -> str:
    """支持中文 + 英文 + 数字 + - _，其它字符替换成 -。"""
    out = SLUG_PATTERN.sub("-", s.strip())
    return out.strip("-")


def project_dir(root: Path, project_name: str) -> Path:
    return root / slug(project_name)


def sku_dir(root: Path, project_name: str, sku_name: str, sku_id: str | None = None) -> Path:
    """SKU 磁盘目录。新格式包含 id 短缀防止同名 SKU 撞库。
    - 新建/读取：传 sku_id，落到 <proj>/<sku_name>-<id8>/
    - 兼容老路径：sku_id 为 None 时退回老格式 <proj>/<sku_name>/（仅迁移脚本使用）
    """
    base = project_dir(root, project_name)
    if sku_id:
        return base / f"{slug(sku_name)}-{sku_id[:8]}"
    return base / slug(sku_name)


def variant_dir(skud: Path, variant) -> Path:
    """变体所属目录。
    - 迁移过来的"默认"变体（src_path 在 sku_d/source/ 下）→ 复用 sku_d，保留旧布局
    - 新建变体（或已用 sku_d/<slug>/source/ 的）→ sku_d/<slug>
    """
    if variant.images:
        first_src = Path(variant.images[0].src_path)
        if first_src.parent == skud / "source":
            return skud
    return skud / slug(variant.color_name)


def source_dir(sku_d: Path) -> Path:
    return sku_d / "source"


def cutout_dir(sku_d: Path) -> Path:
    return sku_d / "cutout"


def master_dir(sku_d: Path) -> Path:
    return sku_d / "master"


def outputs_dir(sku_d: Path) -> Path:
    return sku_d / "outputs"


def platform_dir(sku_d: Path, platform: str) -> Path:
    if platform not in VALID_PLATFORMS:
        raise ValueError(f"invalid platform: {platform}, must be one of {VALID_PLATFORMS}")
    return outputs_dir(sku_d) / platform


def variant_detail_path(sku_d: Path, variant, platform: str) -> Path:
    """该变体在该平台的详情页输出路径。

    位置：outputs/<platform>/<variant_slug>/detail-template.jpg

    每个 variant 一份；不和别的颜色共享。"""
    return platform_dir(sku_d, platform) / slug(variant.color_name) / "detail-template.jpg"


def ensure_sku_dirs(sku_d: Path) -> None:
    """创建 SKU 下所有子目录。"""
    for sub in (source_dir, cutout_dir, master_dir, outputs_dir):
        sub(sku_d).mkdir(parents=True, exist_ok=True)
    for p in VALID_PLATFORMS:
        platform_dir(sku_d, p).mkdir(parents=True, exist_ok=True)
