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


def sku_dir(root: Path, project_name: str, sku_name: str) -> Path:
    return project_dir(root, project_name) / slug(sku_name)


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


def ensure_sku_dirs(sku_d: Path) -> None:
    """创建 SKU 下所有子目录。"""
    for sub in (source_dir, cutout_dir, master_dir, outputs_dir):
        sub(sku_d).mkdir(parents=True, exist_ok=True)
    for p in VALID_PLATFORMS:
        platform_dir(sku_d, p).mkdir(parents=True, exist_ok=True)
