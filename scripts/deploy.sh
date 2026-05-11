#!/usr/bin/env bash
# 把 dev 调好的代码"发布"到 prod：
#   1. 在 prod 数据目录下保留快照（不改动）
#   2. 重启 prod 进程（picks up current git HEAD）
#
# 用法：scripts/deploy.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "deploying HEAD → prod:"
git log --oneline -1

# dev 必须先 commit；提示但不阻塞
if [[ -n "$(git status --porcelain)" ]]; then
  echo ""
  echo "⚠ working tree 有未提交改动，prod 启动将带上这些改动："
  git status --short
  echo ""
  read -r -p "继续？[y/N] " ans
  [[ "$ans" =~ ^[yY]$ ]] || { echo "已取消"; exit 1; }
fi

# 重启 prod
ENV_NAME=prod "$ROOT/scripts/start.sh"

echo ""
echo "✓ deployed"
"$ROOT/scripts/status.sh"
