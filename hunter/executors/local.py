from __future__ import annotations

import ipaddress
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

IOT_UDP_PORTS = "53,67,68,80,443,1900,5353,554,8080"


def host_discovery_probes(on_link: bool) -> list[str]:
    if on_link:
        return ["-PE", "-PP", "-PM", "-PR", "-PS22,80,443,3389,8080", "-PA80,443"]
    return ["-PE", "-PP", "-PS22,80,443,3389,8080", "-PA80,443"]


def ip_in_allowed(ip: str, allowed_cidrs: list[str]) -> bool:
    try:
        target = ipaddress.ip_address(ip)
    except Exception:
        return False
    for cidr in allowed_cidrs:
        try:
            if target in ipaddress.ip_network(cidr, strict=False):
                return True
        except Exception:
            continue
    return False


@dataclass
class LocalExecutor:
    iface: str
    allowed_cidrs: list[str]
    timeout_seconds: int = 180

    def _run(self, argv: list[str], timeout_seconds: int | None = None) -> subprocess.CompletedProcess:
        cmd = ["nmap", "-e", self.iface, *argv]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds or self.timeout_seconds,
            check=False,
        )

    def discover_hosts(self, cidr: str) -> dict[str, Any]:
        net = ipaddress.ip_network(cidr, strict=False)
        if not any(net.subnet_of(ipaddress.ip_network(c, strict=False)) for c in self.allowed_cidrs):
            return {"error": f"Target {cidr} is outside mission scope"}

        probes = host_discovery_probes(on_link=True)
        result = self._run(["-sn", *probes, "-oX", "-", cidr], timeout_seconds=max(self.timeout_seconds, 300))
        if result.returncode != 0 and not result.stdout:
            return {"error": result.stderr.strip() or "nmap discovery failed"}

        hosts: list[str] = []
        try:
            root = ET.fromstring(result.stdout)
            for host in root.findall(".//host"):
                status = host.find("status")
                if status is None or status.get("state") != "up":
                    continue
                addr = host.find("address")
                if addr is None:
                    continue
                ip = str(addr.get("addr") or "")
                if ip and ip_in_allowed(ip, self.allowed_cidrs):
                    hosts.append(ip)
        except ET.ParseError as exc:
            return {"error": f"nmap XML parse failed: {exc}"}

        hosts = sorted(set(hosts), key=lambda x: tuple(int(p) for p in x.split(".")))
        return {"cidr": cidr, "hosts": hosts, "count": len(hosts)}

    def port_scan_light(self, ip: str) -> dict[str, Any]:
        if not ip_in_allowed(ip, self.allowed_cidrs):
            return {"error": f"Target {ip} is outside mission scope"}

        result = self._run(["-sV", "--open", "-T4", "-oX", "-", ip])
        if result.returncode != 0 and not result.stdout:
            return {"error": result.stderr.strip() or "nmap light scan failed"}

        open_ports: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(result.stdout)
            for port in root.findall(".//port"):
                state = port.find("state")
                if state is None or state.get("state") != "open":
                    continue
                service = port.find("service")
                open_ports.append({
                    "port": int(port.get("portid", "0")),
                    "protocol": port.get("protocol", "tcp"),
                    "service": (service.get("name") if service is not None else "") or "unknown",
                    "version": (service.get("version") if service is not None else "") or "",
                })
        except ET.ParseError as exc:
            return {"error": f"nmap XML parse failed: {exc}"}

        return {"ip": ip, "open_ports": open_ports, "count": len(open_ports)}

    def port_scan_iot(self, ip: str) -> dict[str, Any]:
        if not ip_in_allowed(ip, self.allowed_cidrs):
            return {"error": f"Target {ip} is outside mission scope"}

        result = self._run(
            ["-sU", "-p", IOT_UDP_PORTS, "--max-retries", "2", "--host-timeout", "4m", "-oX", "-", ip],
            timeout_seconds=max(self.timeout_seconds, 300),
        )
        if result.returncode != 0 and not result.stdout:
            return {"error": result.stderr.strip() or "nmap iot scan failed"}

        open_ports: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(result.stdout)
            for port in root.findall(".//port"):
                state = port.find("state")
                if state is None:
                    continue
                state_value = state.get("state")
                if state_value not in {"open", "open|filtered"}:
                    continue
                service = port.find("service")
                open_ports.append({
                    "port": int(port.get("portid", "0")),
                    "protocol": port.get("protocol", "udp"),
                    "state": state_value,
                    "service": (service.get("name") if service is not None else "") or "unknown",
                    "version": (service.get("version") if service is not None else "") or "",
                })
        except ET.ParseError as exc:
            return {"error": f"nmap XML parse failed: {exc}"}

        return {"ip": ip, "open_ports": open_ports, "count": len(open_ports), "profile": "iot"}

