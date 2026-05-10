#!/usr/bin/env bash
set -euo pipefail

FONT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/assets/fonts"
mkdir -p "$FONT_DIR"

# Adobe Source Han Sans CN release v2.004
BASE="https://github.com/adobe-fonts/source-han-sans/raw/release/SubsetOTF/CN"
WEIGHTS=("Regular" "Bold" "Heavy")

for w in "${WEIGHTS[@]}"; do
  out="$FONT_DIR/SourceHanSansCN-$w.otf"
  if [ -f "$out" ]; then
    echo "exists: SourceHanSansCN-$w.otf"
    continue
  fi
  echo "downloading SourceHanSansCN-$w.otf ..."
  curl -fsSL "$BASE/SourceHanSansCN-$w.otf" -o "$out"
done

ls -lh "$FONT_DIR" | grep -i "han\|noto" || true
echo "fonts ready in $FONT_DIR"
