#!/usr/bin/env bash
# 看两个环境状态
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

check() {
  local env="$1" bport="$2" fport="$3"
  local b="✗" f="✗"
  curl -sf -o /dev/null "http://127.0.0.1:$bport/api/projects" && b="✓"
  curl -sf -o /dev/null "http://127.0.0.1:$fport"              && f="✓"
  printf "  %-5s backend :%d %s   frontend :%d %s\n" "$env" "$bport" "$b" "$fport" "$f"
}

echo "img2ec services:"
check prod 9000 3010
check dev  9001 3011

echo ""
echo "git: $(cd "$ROOT" && git log --oneline -1)"
