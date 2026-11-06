# Network / RF sensors

Shared `Reporter` (`sensor_reporter.py`) registers agents and posts
`/api/sensor/ingest` with header `X-Sensor-Key` (value from `SENSOR_API_KEY`).

| Module | Role | Notes |
|--------|------|-------|
| `ntopng_sensor.py` | flow / L7 | OPNsense ntopng |
| `opnsense_sensor.py` | gateway | ARP/DHCP/IDS |
| `pihole_sensor.py` | DNS | Pi-hole v6 |
| `wifi_sensor.py` | wireless / RF | **passive summaries only** |

## Wi-Fi / RF (`wifi_sensor.py`)

First Hermes wireless integration for SentinelZero. Registers as
`t470s-rf` / `phasm-T470s` / `192.168.68.111` with `role=wireless` and
tags `rf`, `passive`. Ingests `collectors.system` + `collectors.wifi`
(`aps`, `clients_summary`, `channels`, `events`) about every 60s.
Summaries only, ≤5 KB per wifi block — no pcaps.

### Deferred (hardware PoC — not in this tree)

- Monitor-mode capture daemon, `wifi-mon`, sudoers, tshark
- Live sniffing on `wlx54c9ff02d309` (never touch uplink `wlp58s0`)
- `t470s-rf-mcp` on the laptop (reads local summary DB later)

Until those land, point `summary_path` / `WIFI_SUMMARY_PATH` at a JSON
file when available, or let the sensor ship empty heartbeat summaries so
registration and ingest stay exercised.

Hard rules R1–R7: passive only, own ESS, no cracking, no forge transmit
primitives, never operate `wlp58s0`, never print secrets, payload-free
headers only.

## Hunter SSH executor

See `agent/hunter/executors/ssh.py` — same interface as `LocalExecutor`,
over SSH to a restricted T470s user with a forced-command allow-list
(`nmap` profiles, `rf_whereis`, `rf_clients`). No interactive shell,
no `wifi-mon`, no sudo. Configure via `HUNTER_RF_SSH_*` env vars; do not
embed keys or passwords in config.
