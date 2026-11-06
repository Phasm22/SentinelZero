"""SSH hunter executor — same surface as LocalExecutor, over a restricted hop.

Runs allowed commands on the T470s RF sense host via SSH to a *forced-command*
account. No interactive shell, no wifi-mon, no sudo, no radio control.

Allow-list (forced remote command names):
  - nmap scan profiles mirrored from LocalExecutor:
      discover_hosts, port_scan_light, port_scan_iot
  - RF read-only tools (summary DB / t470s-rf-mcp later):
      rf_whereis, rf_clients

Host config is intentionally not hard-coded beyond the known T470s address
(192.168.68.111). Credentials come from env / constructor args:

  HUNTER_RF_SSH_HOST       default 192.168.68.111
  HUNTER_RF_SSH_USER       restricted account (required to actually run)
  HUNTER_RF_SSH_IDENTITY   path to private key (optional)
  HUNTER_RF_SSH_PORT       default 22

The remote ``authorized_keys`` ForcedCommand should dispatch only the tokens
in ALLOWED_REMOTE_COMMANDS. This module never requests a TTY and never ships
shell metacharacters in the remote argv.

Live capture / wifi-mon / t470s-rf-mcp remain deferred (hardware PoC).
"""
from __future__ import annotations

import ipaddress
import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any

from hunter.executors.local import IOT_UDP_PORTS, ip_in_allowed

DEFAULT_RF_HOST = "192.168.68.111"

# Tokens the remote forced-command wrapper may accept. Keep in sync with the
# restricted user's ForcedCommand dispatcher on the T470s.
ALLOWED_REMOTE_COMMANDS = frozenset({
    "discover_hosts",
    "port_scan_light",
    "port_scan_iot",
    "rf_whereis",
    "rf_clients",
})

# Explicitly refused — never map these onto SSH argv.
REFUSED_REMOTE_COMMANDS = frozenset({
    "wifi-mon",
    "tshark",
    "tcpdump",
    "aireplay-ng",
    "aircrack-ng",
    "sudo",
    "bash",
    "sh",
    "zsh",
})


@dataclass
class SshExecutor:
    """Mirror LocalExecutor methods; execute via restricted SSH.

    When ``user`` is unset, methods return a structured error instead of
    inventing credentials. ``iface`` is accepted for interface parity with
    LocalExecutor but is *not* passed for RF tools (remote wrapper owns ifaces;
    uplink ``wlp58s0`` must never be targeted).
    """

    allowed_cidrs: list[str]
    iface: str = ""
    host: str = field(default_factory=lambda: os.environ.get("HUNTER_RF_SSH_HOST", DEFAULT_RF_HOST))
    user: str = field(default_factory=lambda: os.environ.get("HUNTER_RF_SSH_USER", ""))
    identity_file: str = field(default_factory=lambda: os.environ.get("HUNTER_RF_SSH_IDENTITY", ""))
    port: int = field(default_factory=lambda: int(os.environ.get("HUNTER_RF_SSH_PORT", "22") or "22"))
    timeout_seconds: int = 180

    def _ssh_ready(self) -> str | None:
        if not self.user:
            return (
                "SSH executor not configured: set HUNTER_RF_SSH_USER "
                "(and optionally HUNTER_RF_SSH_IDENTITY) for the restricted T470s account"
            )
        if not self.host:
            return "SSH executor host is empty"
        return None

    def _build_ssh_argv(self, remote_argv: list[str]) -> list[str]:
        # BatchMode + no TTY: never an interactive shell.
        argv = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ConnectTimeout=10",
            "-p", str(self.port),
            "-T",
        ]
        if self.identity_file:
            argv.extend(["-i", self.identity_file])
        argv.append(f"{self.user}@{self.host}")
        # Remote side receives a single allow-listed command token + argv.
        # ForcedCommand on the server should ignore shell and dispatch by token.
        argv.extend(remote_argv)
        return argv

    def _run_allowed(self, command: str, args: list[str], *, timeout_seconds: int | None = None) -> dict[str, Any]:
        if command in REFUSED_REMOTE_COMMANDS:
            return {"error": f"refused remote command: {command}"}
        if command not in ALLOWED_REMOTE_COMMANDS:
            return {"error": f"command not in SSH allow-list: {command}"}

        ready = self._ssh_ready()
        if ready:
            return {"error": ready, "configured": False}

        # No shell metacharacters — each arg is a separate argv element.
        for a in args:
            if not isinstance(a, str) or any(c in a for c in "\n\r;|&$`"):
                return {"error": "refused unsafe remote argument"}

        remote_argv = [command, *args]
        ssh_argv = self._build_ssh_argv(remote_argv)
        try:
            result = subprocess.run(
                ssh_argv,
                capture_output=True,
                text=True,
                timeout=timeout_seconds or self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError:
            return {"error": "ssh binary not found on hunter host"}
        except subprocess.TimeoutExpired:
            return {"error": f"ssh {command} timed out"}

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        if result.returncode != 0 and not stdout:
            return {
                "error": stderr or f"ssh {command} failed (rc={result.returncode})",
                "returncode": result.returncode,
            }

        if not stdout:
            return {"ok": True, "raw": "", "returncode": result.returncode}

        try:
            parsed = json.loads(stdout)
            if isinstance(parsed, dict):
                return parsed
            return {"ok": True, "data": parsed, "returncode": result.returncode}
        except json.JSONDecodeError:
            # Forced-command wrappers may return plain text for rf_whereis.
            return {"ok": True, "raw": stdout, "returncode": result.returncode}

    # --- LocalExecutor-compatible nmap profiles (remote allow-listed) ----------

    def discover_hosts(self, cidr: str) -> dict[str, Any]:
        try:
            net = ipaddress.ip_network(cidr, strict=False)
        except ValueError as exc:
            return {"error": f"invalid cidr: {exc}"}
        if not any(net.subnet_of(ipaddress.ip_network(c, strict=False)) for c in self.allowed_cidrs):
            return {"error": f"Target {cidr} is outside mission scope"}
        return self._run_allowed(
            "discover_hosts",
            [cidr],
            timeout_seconds=max(self.timeout_seconds, 300),
        )

    def port_scan_light(self, ip: str) -> dict[str, Any]:
        if not ip_in_allowed(ip, self.allowed_cidrs):
            return {"error": f"Target {ip} is outside mission scope"}
        return self._run_allowed("port_scan_light", [ip])

    def port_scan_iot(self, ip: str) -> dict[str, Any]:
        if not ip_in_allowed(ip, self.allowed_cidrs):
            return {"error": f"Target {ip} is outside mission scope"}
        return self._run_allowed(
            "port_scan_iot",
            [ip, IOT_UDP_PORTS],
            timeout_seconds=max(self.timeout_seconds, 300),
        )

    # --- RF read-only tools (summary DB / mcp later) ---------------------------

    def rf_whereis(self, mac_or_device: str) -> dict[str, Any]:
        """Ask which AP a client is on (RSSI / last seen). Read-only."""
        target = (mac_or_device or "").strip().lower()
        if not target:
            return {"error": "mac or device id required"}
        return self._run_allowed("rf_whereis", [target])

    def rf_clients(self, bssid_or_device: str = "") -> dict[str, Any]:
        """Associated client summary for a BSSID or mapped device. Read-only."""
        args = [bssid_or_device.strip().lower()] if bssid_or_device.strip() else []
        return self._run_allowed("rf_clients", args)


def allow_list_manifest() -> dict[str, Any]:
    """Document the forced-command allow-list for operators (no secrets)."""
    return {
        "host_default": DEFAULT_RF_HOST,
        "allowed": sorted(ALLOWED_REMOTE_COMMANDS),
        "refused": sorted(REFUSED_REMOTE_COMMANDS),
        "env": [
            "HUNTER_RF_SSH_HOST",
            "HUNTER_RF_SSH_USER",
            "HUNTER_RF_SSH_IDENTITY",
            "HUNTER_RF_SSH_PORT",
        ],
        "notes": [
            "Remote account must use ForceCommand / authorized_keys command= restrictor.",
            "No interactive shell, no sudo, no wifi-mon, no packet capture.",
            "Uplink iface wlp58s0 is never a valid target; sniff iface (deferred) is wlx54c9ff02d309 only.",
            "rf_* tools read local summary DB / t470s-rf-mcp later — hardware PoC deferred.",
        ],
        "example_forced_command_dispatch": (
            "case \"$1\" in "
            "discover_hosts|port_scan_light|port_scan_iot|rf_whereis|rf_clients) "
            "exec /usr/local/lib/sentinel-rf/forced-cmd \"$@\" ;; "
            "*) echo '{\"error\":\"denied\"}' >&2; exit 1 ;; esac"
        ),
    }


__all__ = [
    "SshExecutor",
    "ALLOWED_REMOTE_COMMANDS",
    "REFUSED_REMOTE_COMMANDS",
    "DEFAULT_RF_HOST",
    "allow_list_manifest",
]
