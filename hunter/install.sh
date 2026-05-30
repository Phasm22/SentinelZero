#!/bin/bash
# Install SentinelZero hunter on sentinel-hunter host.
set -euo pipefail

AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HUNTER_DIR="${AGENT_DIR}/hunter"
CONFIG_DIR=/etc/sentinel-hunter

if [[ "${EUID}" -ne 0 ]]; then
  echo "error: must be run as root" >&2
  exit 1
fi

if ! id -u hunter >/dev/null 2>&1; then
  echo "error: expected user 'hunter' on this host" >&2
  exit 1
fi

apt-get update -qq
apt-get install -y --no-install-recommends nmap libcap2-bin curl ca-certificates -qq

if command -v setcap >/dev/null 2>&1 && command -v nmap >/dev/null 2>&1; then
  setcap cap_net_raw,cap_net_admin+ep "$(command -v nmap)" || true
fi

if ! command -v uv >/dev/null 2>&1; then
  sudo -u hunter bash -lc 'curl -LsSf https://astral.sh/uv/install.sh | sh'
fi

sudo -u hunter bash -lc "cd \"${AGENT_DIR}\" && ~/.local/bin/uv sync --python 3.12 || uv sync --python 3.12"

mkdir -p "${CONFIG_DIR}"
chmod 750 "${CONFIG_DIR}"
chown root:hunter "${CONFIG_DIR}"

if [[ ! -f "${CONFIG_DIR}/agent.env" ]]; then
  cat > "${CONFIG_DIR}/agent.env" <<'EOF'
SENTINELZERO_URL=http://172.16.0.254:5000
SENSOR_API_KEY=
OLLAMA_BASE_URL=http://192.168.68.202:11434/v1
OLLAMA_MODEL=qwen2.5:14b
HUNTER_REPORTS_DIR=/home/hunter/agent/reports
HUNTER_LAB_IFACE=enp6s18
HUNTER_HOME_IFACE=enp6s19
EOF
  chmod 640 "${CONFIG_DIR}/agent.env"
  chown root:hunter "${CONFIG_DIR}/agent.env"
fi

install -m 0644 "${HUNTER_DIR}/sentinel-hunter@.service" /etc/systemd/system/sentinel-hunter@.service
install -m 0644 "${HUNTER_DIR}/sentinel-hunter@lab_inventory.timer" /etc/systemd/system/sentinel-hunter@lab_inventory.timer
install -m 0644 "${HUNTER_DIR}/sentinel-hunter@home_inventory.timer" /etc/systemd/system/sentinel-hunter@home_inventory.timer
install -m 0644 "${HUNTER_DIR}/sentinel-hunter-health.service" /etc/systemd/system/sentinel-hunter-health.service
install -m 0644 "${HUNTER_DIR}/sentinel-hunter-health.timer" /etc/systemd/system/sentinel-hunter-health.timer
chmod 0755 "${HUNTER_DIR}/healthcheck.sh"

systemctl daemon-reload
systemctl enable --now sentinel-hunter@lab_inventory.timer sentinel-hunter@home_inventory.timer sentinel-hunter-health.timer

echo "Hunter install complete."
echo "Next: set SENSOR_API_KEY in ${CONFIG_DIR}/agent.env and restart timers if needed."

