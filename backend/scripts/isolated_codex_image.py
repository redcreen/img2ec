#!/usr/bin/env python3
"""Standalone Codex image-generation runner with per-invocation isolation.

Each call creates a fresh temporary ``CODEX_HOME`` containing only ``auth.json``,
starts ``codex exec --ephemeral --enable image_generation``, and reads the PNG
only from this invocation's ``generated_images/<thread_id>/`` directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from PIL import Image


EXIT_OK = 0
EXIT_USAGE = 2
EXIT_ENV = 3
EXIT_TIMEOUT = 5
EXIT_CODEX_FAILED = 6
EXIT_NO_THREAD_ID = 7
EXIT_NO_IMAGE = 8


class ImageGenError(RuntimeError):
    def __init__(self, message: str, *, exit_code: int):
        super().__init__(message)
        self.exit_code = exit_code


class UsageError(ImageGenError):
    def __init__(self, message: str):
        super().__init__(message, exit_code=EXIT_USAGE)


class EnvError(ImageGenError):
    def __init__(self, message: str):
        super().__init__(message, exit_code=EXIT_ENV)


class CodexTimeoutError(ImageGenError):
    def __init__(self, message: str):
        super().__init__(message, exit_code=EXIT_TIMEOUT)


class CodexFailedError(ImageGenError):
    def __init__(self, message: str):
        super().__init__(message, exit_code=EXIT_CODEX_FAILED)


class NoThreadIdError(ImageGenError):
    def __init__(self, message: str):
        super().__init__(message, exit_code=EXIT_NO_THREAD_ID)


class NoImageError(ImageGenError):
    def __init__(self, message: str):
        super().__init__(message, exit_code=EXIT_NO_IMAGE)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _image_info(path: Path) -> dict[str, object]:
    with Image.open(path) as img:
        return {
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "format": img.format,
        }


def _default_real_codex_home() -> Path:
    return Path.home() / ".codex"


@contextmanager
def isolated_codex_home(real_codex_home: Path | None = None) -> Iterator[Path]:
    real = real_codex_home if real_codex_home is not None else _default_real_codex_home()
    if not real.is_dir():
        raise EnvError(f"Codex home directory not found at {real}. Run `codex login` first.")
    auth = real / "auth.json"
    if not auth.is_file():
        raise EnvError(f"{auth} not found. Run `codex login` first.")

    with tempfile.TemporaryDirectory(prefix="img2ec-codex-image-") as td:
        home = Path(td)
        (home / "auth.json").symlink_to(auth)
        yield home


def build_prompt(prompt: str, *, refs: list[Path], size: str = "auto", quality: str = "auto") -> str:
    parts: list[str] = []
    if size != "auto":
        parts.append(f"Generate at size: {size}.")
    if quality != "auto":
        parts.append(f"Quality: {quality}.")
    if refs:
        parts.append("Reference images attached:")
        for idx, ref in enumerate(refs, start=1):
            role = "product subject" if idx == 1 else "additional allowed reference"
            parts.append(f"  Image {idx} = {ref.name} — {role}")
        parts.append("Use the built-in image_generation tool.")
        parts.append("")
        parts.append("User prompt:")
    parts.append(prompt)
    return "\n".join(parts)


def _build_codex_command(refs: list[Path]) -> list[str]:
    cmd = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--ignore-rules",
        "--ephemeral",
        "-s",
        "read-only",
        "--enable",
        "image_generation",
        "--json",
        "--color",
        "never",
    ]
    for ref in refs:
        cmd.extend(["-i", str(ref)])
    return cmd


def _extract_thread_id(stdout: str) -> str:
    first = stdout.lstrip().splitlines()[0] if stdout.strip() else ""
    if not first:
        raise NoThreadIdError("Codex produced no JSON events; cannot identify this session.")
    try:
        event = json.loads(first)
    except json.JSONDecodeError as exc:
        raise NoThreadIdError(f"First Codex event is not JSON: {first[:120]!r}") from exc
    thread_id = event.get("thread_id")
    if not thread_id:
        raise NoThreadIdError(f"First Codex event has no thread_id: {event!r}")
    return str(thread_id)


def _find_generated_png(codex_home: Path, thread_id: str) -> tuple[Path, list[Path]]:
    thread_dir = codex_home / "generated_images" / thread_id
    if not thread_dir.is_dir():
        raise NoImageError(f"No generated_images directory for this session: {thread_dir}")
    pngs = sorted(thread_dir.glob("*.png"))
    if not pngs:
        raise NoImageError(f"No PNG found for this session: {thread_dir}")
    return pngs[0], pngs[1:]


def _run_codex(
    *,
    prompt: str,
    refs: list[Path],
    codex_home: Path,
    timeout_sec: int,
    run_fn=None,
) -> tuple[str, str]:
    run = run_fn if run_fn is not None else subprocess.run
    cmd = _build_codex_command(refs)
    env = {**os.environ, "CODEX_HOME": str(codex_home)}
    try:
        proc = run(
            cmd,
            env=env,
            timeout=timeout_sec,
            capture_output=True,
            text=True,
            check=False,
            input=prompt,
        )
    except subprocess.TimeoutExpired as exc:
        raise CodexTimeoutError(f"codex exec exceeded timeout of {timeout_sec}s") from exc
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or "").splitlines()[-40:])
        raise CodexFailedError(f"codex exec exited {proc.returncode}.\n--- stderr tail ---\n{tail}")
    thread_id = _extract_thread_id(proc.stdout or "")
    return thread_id, proc.stderr or ""


def generate_image(
    *,
    prompt: str,
    out: Path,
    refs: list[Path] | None = None,
    timeout_sec: int = 360,
    manifest: Path | None = None,
    size: str = "auto",
    quality: str = "auto",
    real_codex_home: Path | None = None,
    run_fn=None,
) -> dict[str, object]:
    if not prompt.strip():
        raise UsageError("prompt must not be empty")
    if timeout_sec <= 0:
        raise UsageError("timeout_sec must be positive")

    resolved_refs = [Path(ref).expanduser().resolve() for ref in (refs or [])]
    for ref in resolved_refs:
        if not ref.is_file():
            raise UsageError(f"reference image not found: {ref}")

    out = out.expanduser().resolve()
    invocation_id = uuid.uuid4().hex
    full_prompt = build_prompt(prompt, refs=resolved_refs, size=size, quality=quality)
    temp_home_path = ""
    with isolated_codex_home(real_codex_home) as home:
        temp_home_path = str(home)
        thread_id, stderr = _run_codex(
            prompt=full_prompt,
            refs=resolved_refs,
            codex_home=home,
            timeout_sec=timeout_sec,
            run_fn=run_fn,
        )
        primary, extras = _find_generated_png(home, thread_id)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(primary), str(out))

    result: dict[str, object] = {
        "tool": "isolated_codex_image.py",
        "invocation_id": invocation_id,
        "thread_id": thread_id,
        "output": str(out),
        "refs": [str(ref) for ref in resolved_refs],
        "timeout_sec": timeout_sec,
        "codex_session": {
            "new_temp_codex_home_per_call": True,
            "temp_codex_home": temp_home_path,
            "temp_codex_home_removed": not Path(temp_home_path).exists(),
            "uses_ephemeral_session": True,
            "reads_only_thread_dir": f"generated_images/{thread_id}",
            "global_generated_images_scan": False,
        },
        "output_image": {
            "path": str(out),
            "sha256": _sha256(out),
            **_image_info(out),
        },
    }
    if extras:
        result["discarded_extra_images"] = [p.name for p in extras]
    if stderr.strip():
        result["codex_stderr_tail"] = "\n".join(stderr.splitlines()[-20:])
    if manifest is not None:
        manifest = manifest.expanduser().resolve()
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate one image with an isolated fresh Codex session.")
    prompt_group = p.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt")
    prompt_group.add_argument("--prompt-file", type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--ref", action="append", default=[], type=Path, dest="refs")
    p.add_argument("--timeout-sec", type=int, default=360)
    p.add_argument("--manifest", type=Path)
    p.add_argument("--size", default="auto")
    p.add_argument("--quality", default="auto", choices=["low", "medium", "high", "auto"])
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    prompt = args.prompt if args.prompt is not None else args.prompt_file.read_text(encoding="utf-8")
    manifest = args.manifest or args.out.with_suffix(args.out.suffix + ".manifest.json")
    try:
        result = generate_image(
            prompt=prompt,
            out=args.out,
            refs=args.refs,
            timeout_sec=args.timeout_sec,
            manifest=manifest,
            size=args.size,
            quality=args.quality,
        )
    except ImageGenError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return exc.exit_code
    print(result["output"])
    print(f"thread_id: {result['thread_id']}")
    print(f"manifest: {manifest.expanduser().resolve()}")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
