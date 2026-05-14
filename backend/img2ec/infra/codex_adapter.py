"""Adapter around the codex-imagen skill.

Why a separate layer:
- codex_image.py 以前直接 `import gen` 从 ~/.codex/skills/codex-imagen/scripts/。
  这让单测难做 —— 必须 mock gen 的内部，或真跑 codex CLI。
- 本文件提供唯一的"调 codex-imagen"入口；测试时只 mock 这一层。
- 同时给 codex-imagen API 不稳定时一个集中改的位置。

公开 API:
    generate_image(prompt, out_path, *, refs=None, timeout_sec=600) -> Path
    AdapterError —— 包装 gen.GenError，让上层只需 catch 一个类
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

_SKILL_SCRIPTS = Path.home() / ".codex/skills/codex-imagen/scripts"


class AdapterError(RuntimeError):
    """Adapter 层统一错误。"""

    def __init__(self, msg: str, *, refusal: bool = False) -> None:
        super().__init__(msg)
        self.refusal = refusal


def _load_gen():
    """Lazy import gen.py — 避免 module 加载时就 fail（方便 mock）。"""
    if not (_SKILL_SCRIPTS / "gen.py").is_file():
        raise AdapterError(
            "codex-imagen skill not installed at ~/.codex/skills/codex-imagen/. "
            "Install via the codex-imagen project's scripts/install.sh."
        )
    if str(_SKILL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SKILL_SCRIPTS))
    import gen  # type: ignore
    return gen


_REFUSAL_HINTS = ("refused to invoke", "image_generation", "No PNG produced", "directory does not exist")


def is_refusal(msg: str) -> bool:
    return any(h in msg for h in _REFUSAL_HINTS)


def generate_image(
    prompt: str,
    out_path: Path,
    *,
    refs: Iterable[Path] | None = None,
    timeout_sec: int = 600,
) -> Path:
    """生成一张图到 out_path。

    Raises:
        AdapterError(refusal=True)  — 模型拒绝调 image_generation 工具（可重试）
        AdapterError(refusal=False) — 其它失败（auth、超时、磁盘等）
    """
    gen = _load_gen()
    ref_list = list(refs) if refs else None
    try:
        gen.generate(prompt, out_path, refs=ref_list, timeout_sec=timeout_sec)
    except gen.GenError as e:
        msg = str(e)
        raise AdapterError(msg, refusal=is_refusal(msg)) from e
    return out_path
