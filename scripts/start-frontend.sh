#!/usr/bin/env bash
# Start Vite on 3173 when systemd is unavailable (no sudo).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/frontend/react-sentinelzero"
LOG_DIR="${HOME}/.local/log"
PID_FILE="${HOME}/.local/run/vite-frontend.pid"
NODE="${HOME}/.nvm/versions/node/v22.18.0/bin"
export PATH="$NODE:$PATH"

mkdir -p "$LOG_DIR" "$(dirname "$PID_FILE")"
pkill -f 'react-sentinelzero/node_modules/.bin/vite' 2>/dev/null || true
sleep 1

cd "$FRONTEND"
nohup npm run dev -- --host 0.0.0.0 >>"$LOG_DIR/vite-frontend.log" 2>&1 &
echo $! >"$PID_FILE"
sleep 3
if curl -sf -o /dev/null "http://127.0.0.1:3173/"; then
  echo "Frontend OK: http://localhost:3173/"
else
  echo "Frontend failed — see $LOG_DIR/vite-frontend.log" >&2
  exit 1
fi
