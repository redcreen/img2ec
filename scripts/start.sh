#!/usr/bin/env bash
# 启动一个环境：ENV_NAME=prod|dev scripts/start.sh
# - 自动 kill 老进程，重新拉起后端 + 前端
# - 后台运行，日志写到 .logs/{env}-{backend,frontend}.log
set -euo pipefail
source "$(dirname "$0")/lib.sh"

cd "$ROOT"

echo "[$ENV_NAME] using DATA_ROOT=$DATA_ROOT DB_FILE=$DB_FILE"
echo "[$ENV_NAME] backend :$BACKEND_PORT  frontend :$FRONTEND_PORT"

kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"

# --- 后端 ---
(
  cd "$BACKEND_DIR"
  export IMG2EC_DB_URL="sqlite:///$DB_FILE"
  export IMG2EC_ROOT_PATH="$DATA_ROOT"
  export IMG2EC_CELERY_EAGER=true
  export IMG2EC_CORS_ORIGINS="[\"http://localhost:$FRONTEND_PORT\"]"
  # 自动跑 alembic（确保 DB schema 最新）
  .venv/bin/alembic upgrade head >>"$LOG_DIR/$ENV_NAME-backend.log" 2>&1 || true
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
echo "   web → http://localhost:$FRONTEND_PORT"
echo "   api → http://localhost:$BACKEND_PORT"
echo "   logs → $LOG_DIR/$ENV_NAME-{backend,frontend}.log"
