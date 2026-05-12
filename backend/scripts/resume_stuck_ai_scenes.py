"""重派所有 category='AI · ... · 生成中' 的占位场景到 celery 队列。

适用场景：早期没用 celery 时 threading.Thread 派的任务被 uvicorn reload 打死，
DB 里留下 "⏳ AI 生成中" 卡片，无人接手。

用法：
    cd backend && IMG2EC_DB_URL=... IMG2EC_REDIS_URL=redis://localhost:6379/1 \
        .venv/bin/python scripts/resume_stuck_ai_scenes.py
"""
from __future__ import annotations
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from img2ec.config import get_settings
from img2ec.tasks.scene_tasks import fill_ai_scene_task  # noqa: E402


def main() -> None:
    db_url = get_settings().db_url
    # 解析 sqlite:///path → path
    db_path = db_url.replace("sqlite:///", "")
    c = sqlite3.connect(db_path); c.row_factory = sqlite3.Row
    n = 0
    fail = 0
    for r in c.execute("""SELECT id, name, festival, desc FROM scenes
                          WHERE category LIKE '%生成中%'"""):
        m = re.match(r"关键词：(.+?)\s*·\s*风格：(.+)", r["desc"] or "")
        if not m:
            print(f"  SKIP {r['id'][:8]}: desc 无法解析 — {r['desc']!r}")
            fail += 1
            continue
        kws = [k.strip() for k in m.group(1).split(",") if k.strip()]
        style = m.group(2).strip()
        print(f"  ENQUEUE {r['id'][:8]} [{r['festival']}] kws={kws} style={style}")
        fill_ai_scene_task.delay(r["id"], kws, r["festival"], style)
        n += 1
    print(f"\n  re-queued: {n}  failed-to-parse: {fail}")


if __name__ == "__main__":
    main()
