#!/usr/bin/env python3
"""Generate a Duanwu e-commerce poster probe through codex-imagen.

This script is intentionally stricter than a general image-to-image runner:
the product photo is the only generation reference. Any comparison image is
recorded only in the manifest after generation and is never passed to Codex.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import isolated_codex_image as _image_runner  # noqa: E402


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_prompt() -> str:
    return """Use case: ads-marketing
Asset type: original vertical Douyin e-commerce detail poster background, 1024x1536.
Input images: Image 1 is the only visual reference and the exact product subject.

Primary request:
Generate a new original Dragon Boat Festival e-commerce detail poster for the product in Image 1.
Do not imitate any existing finished poster. Create a fresh composition from the product only.

Product invariants:
Preserve the Image 1 product as a golden satin fabric mugwort sachet pendant: soft stuffed
handmade tiger-like folk-craft shape, gold hanging cord, rounded seams, satin sheen, subtle
jacquard embroidery texture, warm golden-yellow color. Keep it as fabric. Do not turn it into
a real animal, ceramic object, plastic toy, metal ornament, or a different product.

Scene and layout:
Create a fresh premium guofeng Duanwu composition with warm wood, cream rice-paper panels,
mugwort, calamus, zongzi leaves, soft window light, and gift-giving atmosphere. Use a clean
modular detail-page structure: one large hero product scene, product information blank panel,
usage-scene thumbnails, detail texture cards, mugwort filling atmosphere card, and gift box
scene. Leave generous blank label areas for later Chinese typography.

Text handling:
Prefer no small text. If any text appears, keep only short clear Chinese festival words.
Never generate English, watermark, logo, dense fine print, or illegible text-like marks.

Quality:
High-resolution commercial photography look, sharp product, visible satin highlights and
embroidery texture, natural contact shadow, warm sunlight, clean professional e-commerce design.
"""


def _image_info(path: Path) -> dict[str, object]:
    with Image.open(path) as img:
        return {
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "format": img.format,
        }


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_manifest(
    *,
    path: Path,
    product_image: Path,
    out: Path,
    prompt_path: Path,
    compare_against: Path | None,
    timeout_sec: int,
    image_result: dict[str, object],
) -> None:
    data: dict[str, object] = {
        "tool": "duanwu_codex_imagen_probe.py",
        "generation_refs": [str(product_image)],
        "output": str(out),
        "prompt_path": str(prompt_path),
        "timeout_sec": timeout_sec,
        "isolation": image_result.get("codex_session", {}),
        "thread_id": image_result.get("thread_id"),
        "invocation_id": image_result.get("invocation_id"),
        "product_image": {
            "path": str(product_image),
            "sha256": _sha256(product_image),
            **_image_info(product_image),
        },
        "output_image": {
            "path": str(out),
            "sha256": _sha256(out),
            **_image_info(out),
        },
    }
    if compare_against is not None:
        data["compare_against"] = str(compare_against)
        data["comparison_note"] = (
            "This image is for post-generation review only and was not passed as a generation ref."
        )
        data["compare_image"] = {
            "path": str(compare_against),
            "sha256": _sha256(compare_against),
            **_image_info(compare_against),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Generate a Duanwu poster probe without using any target poster as a ref."
    )
    p.add_argument("--product-image", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--compare-against", type=Path)
    p.add_argument("--manifest", type=Path)
    p.add_argument("--prompt-out", type=Path)
    p.add_argument("--timeout-sec", type=int, default=360)
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    product = args.product_image.expanduser().resolve()
    out = args.out.expanduser().resolve()
    compare = args.compare_against.expanduser().resolve() if args.compare_against else None
    prompt_path = (
        args.prompt_out.expanduser().resolve()
        if args.prompt_out
        else out.with_suffix(out.suffix + ".prompt.txt")
    )
    manifest = (
        args.manifest.expanduser().resolve()
        if args.manifest
        else out.with_suffix(out.suffix + ".manifest.json")
    )

    if not product.is_file():
        print(f"FAIL: product image not found: {product}", file=sys.stderr)
        return 2
    if compare is not None and not compare.is_file():
        print(f"FAIL: comparison image not found: {compare}", file=sys.stderr)
        return 2
    if args.timeout_sec <= 0:
        print("FAIL: --timeout-sec must be positive", file=sys.stderr)
        return 2

    prompt = build_prompt()
    _write_text(prompt_path, prompt)
    if args.dry_run:
        print(f"DRY RUN: prompt written to {prompt_path}")
        print(f"DRY RUN: generation refs would be: {product}")
        return 0

    try:
        image_result = _image_runner.generate_image(
            prompt=prompt,
            out=out,
            refs=[product],
            timeout_sec=args.timeout_sec,
        )
    except _image_runner.ImageGenError as exc:
        print(f"FAIL: isolated Codex image generation: {exc}", file=sys.stderr)
        return exc.exit_code

    _write_manifest(
        path=manifest,
        product_image=product,
        out=out,
        prompt_path=prompt_path,
        compare_against=compare,
        timeout_sec=args.timeout_sec,
        image_result=image_result,
    )
    print(str(out))
    print(f"prompt: {prompt_path}")
    print(f"manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
