#!/usr/bin/env bash
# Wait for SentinelZero backend before starting a sensor (best-effort, max ~120s).
set -euo pipefail

URL="${SENTINEL_BACKEND_URL:-http://127.0.0.1:5000/api/sensor/agents}"
MAX_ATTEMPTS="${SENTINEL_BACKEND_WAIT_ATTEMPTS:-60}"
SLEEP_SEC="${SENTINEL_BACKEND_WAIT_SLEEP:-2}"

for ((i = 1; i <= MAX_ATTEMPTS; i++)); do
  if curl -sf --max-time 2 "$URL" >/dev/null 2>&1; then
    exit 0
  fi
  sleep "$SLEEP_SEC"
done

echo "sentinel sensor: backend not ready at $URL — starting anyway (ingest auto-registers)" >&2
exit 0
