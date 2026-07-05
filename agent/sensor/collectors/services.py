"""Systemd service status collector — active and failed services only."""
import subprocess

_CAP = 100


def collect_services() -> list:
    try:
        result = subprocess.run(
            ['systemctl', 'list-units', '--type=service', '--no-pager', '--no-legend'],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    services = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        unit, load, active, sub = parts[0], parts[1], parts[2], parts[3]
        if active not in ('active', 'failed'):
            continue
        services.append({
            'name': unit.removesuffix('.service'),
            'state': active,
            'sub_state': sub,
        })
        if len(services) >= _CAP:
            break

    return services
