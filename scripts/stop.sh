#!/usr/bin/env bash
# 停止一个环境：ENV_NAME=prod|dev scripts/stop.sh
set -euo pipefail
source "$(dirname "$0")/lib.sh"

kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"
# celery worker
if [[ -f "$LOG_DIR/$ENV_NAME-worker.pid" ]]; then
  WPID=$(cat "$LOG_DIR/$ENV_NAME-worker.pid")
  if [[ -n "$WPID" ]] && kill -0 "$WPID" 2>/dev/null; then
    kill -TERM "$WPID" 2>/dev/null || true
    sleep 2
    kill -KILL "$WPID" 2>/dev/null || true
  fi
fi
rm -f "$LOG_DIR/$ENV_NAME-backend.pid" "$LOG_DIR/$ENV_NAME-frontend.pid" "$LOG_DIR/$ENV_NAME-worker.pid"
echo "[$ENV_NAME] stopped"
