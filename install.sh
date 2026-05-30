#!/bin/bash
# Install and configure the SentinelZero analysis agent on this host.
# Must be run as root (uses systemctl, creates /etc directories).
#
# After install:
#   1. Set ANTHROPIC_API_KEY in /etc/sentinel-agent/agent.env
#   2. systemctl start sentinel-agent   (one-shot run)
#      OR
#      systemctl enable --now sentinel-agent.timer  (periodic, every 30 min)

set -euo pipefail

AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR=/etc/sentinel-agent
UV="${HOME}/.local/bin/uv"

if [[ "${EUID}" -ne 0 ]]; then
    echo "error: must be run as root" >&2
    exit 1
fi

echo "==> SentinelZero agent install (${AGENT_DIR})"

# ── 1. Ensure uv is available ─────────────────────────────────────────────
if ! command -v uv &>/dev/null && [[ ! -x "${UV}" ]]; then
    echo "==> Installing uv..."
    apt-get install -y curl --no-install-recommends -qq
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Prefer system-wide uv, fall back to user install
if command -v uv &>/dev/null; then
    UV_CMD=uv
else
    UV_CMD="${UV}"
fi

# ── 2. Sync Python environment ─────────────────────────────────────────────
echo "==> Syncing Python environment..."
cd "${AGENT_DIR}"
"${UV_CMD}" sync --python 3.12

# ── 3. Create config directory and env file ────────────────────────────────
mkdir -p "${CONFIG_DIR}"
chmod 750 "${CONFIG_DIR}"
chown root:sentinel "${CONFIG_DIR}"

if [[ ! -f "${CONFIG_DIR}/agent.env" ]]; then
    cat > "${CONFIG_DIR}/agent.env" <<'EOF'
# SentinelZero analysis agent environment — root:sentinel 640
OPENAI_API_KEY=
# Model to use (default: gpt-4o-mini; use gpt-4o for higher quality)
# OPENAI_MODEL=gpt-4o-mini
# Optional overrides
# SENTINELZERO_URL=http://172.16.0.254:5000
# SENSOR_API_KEY=
EOF
    chmod 640 "${CONFIG_DIR}/agent.env"
    chown root:sentinel "${CONFIG_DIR}/agent.env"
    echo ""
    echo "  ACTION REQUIRED: set ANTHROPIC_API_KEY in ${CONFIG_DIR}/agent.env"
    echo ""
else
    echo "==> ${CONFIG_DIR}/agent.env exists — preserving"
fi

# ── 4. Install systemd units ───────────────────────────────────────────────
echo "==> Installing systemd units..."
cp "${AGENT_DIR}/sentinel-agent.service"  /etc/systemd/system/
cp "${AGENT_DIR}/sentinel-agent.timer"    /etc/systemd/system/
systemctl daemon-reload

echo ""
echo "==> Install complete."
echo ""
echo "    One-shot run  : systemctl start sentinel-agent"
echo "    Enable timer  : systemctl enable --now sentinel-agent.timer"
echo "    Timer status  : systemctl list-timers sentinel-agent.timer"
echo "    Logs          : journalctl -u sentinel-agent -f"
