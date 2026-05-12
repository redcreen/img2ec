"""一次性迁移：把所有 SKU 的磁盘目录从 <proj>/<name>/ 改成 <proj>/<name>-<id8>/，
并更新 DB 里所有绝对路径字段。

用法：
    cd backend && \
    IMG2EC_DB_URL=sqlite:///$HOME/img2ec-dev/img2ec.db \
    IMG2EC_ROOT_PATH=$HOME/img2ec-dev/projects \
    .venv/bin/python scripts/migrate_sku_paths.py

幂等：已经迁移过的 SKU 跳过（new 目录已存在）。
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from img2ec.config import get_settings
from img2ec.db import SessionLocal
from img2ec.infra.fs_layout import slug
from img2ec.models import SKU, Project, Variant, SourceImage


def main() -> None:
    settings = get_settings()
    root = settings.root_path
    db = SessionLocal()
    moved = 0
    skipped = 0
    db_only = 0
    try:
        for sku in db.query(SKU).all():
            proj = db.get(Project, sku.project_id)
            if proj is None:
                continue
            old_dir = Path(proj.root_path) / slug(sku.name)
            new_dir = Path(proj.root_path) / f"{slug(sku.name)}-{sku.id[:8]}"
            if new_dir.exists() and not old_dir.exists():
                skipped += 1
                continue
            old_dir_str = str(old_dir)
            new_dir_str = str(new_dir)
            # 1) 重命名磁盘目录
            if old_dir.exists() and not new_dir.exists():
                old_dir.rename(new_dir)
                print(f"  moved: {old_dir.name} → {new_dir.name}  (sku {sku.id[:8]} {sku.name!r})")
                moved += 1
            else:
                print(f"  db-only update: sku {sku.id[:8]} {sku.name!r}  (no disk dir to rename)")
                db_only += 1

            def fix(s: str) -> str:
                """把字符串里 old_dir_str 替换成 new_dir_str（前缀匹配 + path 分隔符 / 终结符）"""
                if s and s.startswith(old_dir_str + "/"):
                    return new_dir_str + s[len(old_dir_str):]
                if s == old_dir_str:
                    return new_dir_str
                return s

            for variant in sku.variants:
                # variant.sku_thumb_path / sku_thumb_paths
                if variant.sku_thumb_path:
                    variant.sku_thumb_path = fix(variant.sku_thumb_path)
                if variant.sku_thumb_paths:
                    variant.sku_thumb_paths = [fix(p) for p in variant.sku_thumb_paths]
                for img in variant.images:
                    img.src_path = fix(img.src_path)
                    if img.master_paths:
                        img.master_paths = {k: fix(v) for k, v in img.master_paths.items()}
                    if img.master_history:
                        img.master_history = {k: [fix(p) for p in lst] for k, lst in img.master_history.items()}
                    if img.derived_paths:
                        img.derived_paths = {k: fix(v) for k, v in img.derived_paths.items()}
            db.commit()
    finally:
        db.close()
    print()
    print(f"summary: moved={moved}  skipped(already-new)={skipped}  db-only={db_only}")


if __name__ == "__main__":
    main()
