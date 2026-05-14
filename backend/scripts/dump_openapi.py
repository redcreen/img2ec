"""一键导出 OpenAPI schema 到 docs/openapi.json。

用法：
    cd backend && .venv/bin/python scripts/dump_openapi.py

输出会被 frontend 的 openapi-typescript 用来生成 lib/api.gen.ts。
"""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("IMG2EC_ROOT_PATH", str(ROOT / ".tmp-openapi"))
os.environ.setdefault("IMG2EC_DB_URL", "sqlite:///:memory:")

from img2ec.main import app

repo_root = ROOT.parent
out = repo_root / "docs" / "openapi.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2))
print(f"wrote {out} ({len(out.read_text())} bytes, {len(app.openapi().get('paths', {}))} paths)")
