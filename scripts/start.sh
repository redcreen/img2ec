#!/usr/bin/env bash
# 启动一个环境：ENV_NAME=prod|dev scripts/start.sh
# - 自动 kill 老进程，重新拉起后端 + celery worker + 前端
# - 后台运行，日志写到 .logs/{env}-{backend,worker,frontend}.log
set -euo pipefail
source "$(dirname "$0")/lib.sh"

cd "$ROOT"

echo "[$ENV_NAME] DATA_ROOT=$DATA_ROOT  DB=$DB_FILE"
echo "[$ENV_NAME] backend :$BACKEND_PORT  frontend :$FRONTEND_PORT  redis=$REDIS_URL"

# 检查 Redis 在跑
if ! redis-cli ping > /dev/null 2>&1; then
  echo "[$ENV_NAME] Redis 没启动，先尝试 brew services start redis…"
  brew services start redis 2>&1 | tail -3
  sleep 1
  redis-cli ping > /dev/null 2>&1 || { echo "Redis 启动失败" >&2; exit 1; }
fi

kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"

# 也停掉本 env 的老 celery worker
WORKER_PID_FILE="$LOG_DIR/$ENV_NAME-worker.pid"
if [[ -f "$WORKER_PID_FILE" ]]; then
  OLD_WPID=$(cat "$WORKER_PID_FILE" 2>/dev/null || echo "")
  if [[ -n "$OLD_WPID" ]] && kill -0 "$OLD_WPID" 2>/dev/null; then
    echo "[$ENV_NAME] killing old celery worker pid=$OLD_WPID"
    kill -TERM "$OLD_WPID" 2>/dev/null || true
    sleep 2
    kill -KILL "$OLD_WPID" 2>/dev/null || true
  fi
  rm -f "$WORKER_PID_FILE"
fi

EXPORTS_COMMON=(
  "IMG2EC_DB_URL=sqlite:///$DB_FILE"
  "IMG2EC_ROOT_PATH=$DATA_ROOT"
  "IMG2EC_REDIS_URL=$REDIS_URL"
  "IMG2EC_CELERY_EAGER=false"
  "IMG2EC_CORS_ORIGINS=[\"http://localhost:$FRONTEND_PORT\"]"
)

# --- 数据库迁移 ---
(
  cd "$BACKEND_DIR"
  for kv in "${EXPORTS_COMMON[@]}"; do export "$kv"; done
  .venv/bin/alembic upgrade head >>"$LOG_DIR/$ENV_NAME-backend.log" 2>&1 || true
)

# --- Celery worker（独立进程，不受 uvicorn reload 影响） ---
(
  cd "$BACKEND_DIR"
  for kv in "${EXPORTS_COMMON[@]}"; do export "$kv"; done
  # concurrency 默认 4；前端可在线调整（pool_grow/pool_shrink）
  nohup .venv/bin/celery -A img2ec.celery_app worker \
      --concurrency=4 --loglevel=info \
      --hostname="$ENV_NAME-worker@%h" \
      >>"$LOG_DIR/$ENV_NAME-worker.log" 2>&1 &
  echo $! > "$LOG_DIR/$ENV_NAME-worker.pid"
)

# --- 后端 ---
(
  cd "$BACKEND_DIR"
  for kv in "${EXPORTS_COMMON[@]}"; do export "$kv"; done
  nohup .venv/bin/uvicorn img2ec.main:app \
      --host 127.0.0.1 --port "$BACKEND_PORT" $RELOAD_FLAG \
      >>"$LOG_DIR/$ENV_NAME-backend.log" 2>&1 &
  echo $! > "$LOG_DIR/$ENV_NAME-backend.pid"
)

wait_http "http://127.0.0.1:$BACKEND_PORT/api/projects" "backend"

# --- 前端 ---
(
  cd "$FRONTEND_DIR"
  export API_PROXY_TARGET="http://localhost:$BACKEND_PORT"
  nohup npx next dev -p "$FRONTEND_PORT" \
      >>"$LOG_DIR/$ENV_NAME-frontend.log" 2>&1 &
  echo $! > "$LOG_DIR/$ENV_NAME-frontend.pid"
)

wait_http "http://127.0.0.1:$FRONTEND_PORT" "frontend"

echo ""
echo "[$ENV_NAME] up:"
echo "   web    → http://localhost:$FRONTEND_PORT"
echo "   api    → http://localhost:$BACKEND_PORT"
echo "   worker → celery (pid $(cat "$LOG_DIR/$ENV_NAME-worker.pid"))"
echo "   logs   → $LOG_DIR/$ENV_NAME-{backend,worker,frontend}.log"
