#!/usr/bin/env bash
# 公共：判 env、kill 端口、tmux 包装
# 用法：source "$(dirname "$0")/lib.sh"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
LOG_DIR="$ROOT/.logs"
mkdir -p "$LOG_DIR"

# env 名 → port 与数据根
case "${ENV_NAME:-}" in
  prod)
    BACKEND_PORT=9000
    FRONTEND_PORT=3010
    DATA_ROOT="$HOME/img2ec/projects"
    DB_FILE="$HOME/img2ec/img2ec.db"
    RELOAD_FLAG=""
    SESSION="img2ec-prod"
    ;;
  dev)
    BACKEND_PORT=9001
    FRONTEND_PORT=3011
    DATA_ROOT="$HOME/img2ec-dev/projects"
    DB_FILE="$HOME/img2ec-dev/img2ec.db"
    RELOAD_FLAG="--reload"
    SESSION="img2ec-dev"
    ;;
  *)
    echo "ENV_NAME 必须是 prod 或 dev" >&2; exit 2 ;;
esac

mkdir -p "$DATA_ROOT" "$(dirname "$DB_FILE")"

kill_port() {
  local port="$1"
  local pids
  pids=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    echo "[$ENV_NAME] killing pids on :$port → $pids"
    kill $pids 2>/dev/null || true
    sleep 1
    pids=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)
    [[ -n "$pids" ]] && kill -9 $pids 2>/dev/null || true
  fi
}

wait_http() {
  local url="$1" name="$2" tries=40
  for ((i=1;i<=tries;i++)); do
    if curl -sf -o /dev/null "$url"; then
      echo "[$ENV_NAME] $name ready ($url)"
      return 0
    fi
    sleep 0.5
  done
  echo "[$ENV_NAME] $name 启动超时 ($url)" >&2
  return 1
}
