#!/bin/bash
# Deploy sentinel-sensor to a remote host via rsync + uv.
# Usage: ./deploy.sh <target_host> [role]
# Example: ./deploy.sh proxBig.prox proxmox-node
#          ./deploy.sh root@192.168.68.202 linux-server

set -euo pipefail

TARGET="${1:?Usage: $0 <target_host> [role]}"
TARGET="${TARGET##*@}"          # strip user@ prefix — always connects as root
ROLE="${2:-linux-server}"
SENSOR_DIR=/opt/sentinel-sensor
CONFIG_DIR=/etc/sentinel-sensor
STATE_DIR=/var/lib/sentinel-sensor
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH="ssh -o StrictHostKeyChecking=accept-new"

echo "==> Deploying sentinel-sensor to ${TARGET} (role: ${ROLE})"

# 1. Create remote directories
${SSH} "root@${TARGET}" "mkdir -p ${SENSOR_DIR} ${CONFIG_DIR} ${STATE_DIR}"

# 2. Sync sensor files — exclude build artifacts and local venv
rsync -az --delete -e "ssh -o StrictHostKeyChecking=accept-new" \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='.git' \
    --exclude='deploy.sh' \
    "${SCRIPT_DIR}/" "root@${TARGET}:${SENSOR_DIR}/"

# 3. Install uv if not already present, then sync the venv
${SSH} "root@${TARGET}" "
    set -euo pipefail
    if ! command -v uv &>/dev/null; then
        echo '==> Installing uv...'
        apt-get install -y curl --no-install-recommends -qq
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH=\"\$HOME/.local/bin:\$PATH\"
    fi
    export PATH=\"\$HOME/.local/bin:\$PATH\"
    cd ${SENSOR_DIR}
    echo '==> Syncing Python environment with uv...'
    uv sync --python 3.12
    echo '==> Python environment ready.'
"

# 4. Install config only if not already present (never overwrite existing key)
${SSH} "root@${TARGET}" "
    if [ ! -f ${CONFIG_DIR}/config.yaml ]; then
        cp ${SENSOR_DIR}/config.yaml.template ${CONFIG_DIR}/config.yaml
        sed -i 's/role: \"proxmox-node\"/role: \"${ROLE}\"/' ${CONFIG_DIR}/config.yaml
        echo ''
        echo 'ACTION REQUIRED: edit ${CONFIG_DIR}/config.yaml on ${TARGET}'
        echo '  Set agent_id  — unique name for this host (e.g. proxbig)'
        echo '  Set api_key   — match SENSOR_API_KEY in SentinelZero .env'
        echo '  Set host_ip   — this host IP (e.g. 172.16.0.10)'
        echo ''
    else
        echo 'Config exists — preserving ${CONFIG_DIR}/config.yaml'
    fi
"

# 5. Install and enable systemd service
${SSH} "root@${TARGET}" "
    cp ${SENSOR_DIR}/sentinel-sensor.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable sentinel-sensor
"

echo ""
echo "==> Deploy complete: ${TARGET}"
echo "    Edit config : ssh root@${TARGET} vi ${CONFIG_DIR}/config.yaml"
echo "    Start       : ssh root@${TARGET} systemctl start sentinel-sensor"
echo "    Logs        : ssh root@${TARGET} journalctl -u sentinel-sensor -f"
