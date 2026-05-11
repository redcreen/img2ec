#!/usr/bin/env bash
# 停止一个环境：ENV_NAME=prod|dev scripts/stop.sh
set -euo pipefail
source "$(dirname "$0")/lib.sh"

kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"
rm -f "$LOG_DIR/$ENV_NAME-backend.pid" "$LOG_DIR/$ENV_NAME-frontend.pid"
echo "[$ENV_NAME] stopped"
