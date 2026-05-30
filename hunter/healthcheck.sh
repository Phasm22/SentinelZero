#!/bin/bash
set -euo pipefail

ENV_FILE=/etc/sentinel-hunter/agent.env
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}"
  set +a
fi

errors=()

if ! curl -sf "${SENTINELZERO_URL}/api/sensor/agents" >/dev/null; then
  errors+=("sensor_api")
fi

if ! curl -sf "${OLLAMA_BASE_URL}/models" >/dev/null; then
  errors+=("ollama_models")
fi

if [[ "$(systemctl is-active sentinel-hunter@lab_inventory.timer || true)" != "active" ]]; then
  errors+=("lab_timer")
fi

if [[ "$(systemctl is-active sentinel-hunter@home_inventory.timer || true)" != "active" ]]; then
  errors+=("home_timer")
fi

if [[ "${#errors[@]}" -gt 0 ]]; then
  printf '{"status":"error","checks_failed":[%s]}\n' "$(printf '"%s",' "${errors[@]}" | sed 's/,$//')"
  exit 1
fi

echo '{"status":"ok","checks":["sensor_api","ollama_models","lab_timer","home_timer"]}'

