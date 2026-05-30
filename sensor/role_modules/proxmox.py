"""
Proxmox-specific collector — queries pvesh for VM/LXC list and node status.

Only runs when role=proxmox-node. If pvesh is not in PATH the sensor's
graceful-degradation wrapper catches the FileNotFoundError and records the error
without crashing other collectors.
"""
import json
import socket
import subprocess


def _pvesh(path: str) -> dict | list:
    result = subprocess.run(
        ['pvesh', 'get', path, '--output-format=json'],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(f'pvesh {path} exited {result.returncode}: {result.stderr.strip()[:200]}')
    return json.loads(result.stdout)


def collect_proxmox() -> dict:
    node = socket.gethostname()

    node_status = _pvesh(f'/nodes/{node}/status')

    vms_raw = _pvesh(f'/nodes/{node}/qemu')
    lxc_raw = _pvesh(f'/nodes/{node}/lxc')

    def _vm_entry(v: dict, vtype: str) -> dict:
        max_mem = v.get('maxmem') or 1
        return {
            'vmid': v.get('vmid'),
            'name': v.get('name', f'{vtype}-{v.get("vmid")}'),
            'type': vtype,
            'status': v.get('status'),
            'cpu': round(v.get('cpu', 0), 4),
            'mem_pct': round((v.get('mem', 0) / max_mem) * 100, 1),
            'uptime_s': v.get('uptime'),
        }

    guests = [_vm_entry(v, 'qemu') for v in (vms_raw or [])]
    guests += [_vm_entry(v, 'lxc') for v in (lxc_raw or [])]

    mem = node_status.get('memory', {})
    mem_used = mem.get('used', 0)
    mem_total = mem.get('total') or 1

    return {
        'node': node,
        'node_status': node_status.get('status', 'unknown'),
        'cpu_usage_pct': round(node_status.get('cpu', 0) * 100, 1),
        'mem_pct': round((mem_used / mem_total) * 100, 1),
        'guests': guests,
        'guest_count': len(guests),
        'running_guests': sum(1 for g in guests if g.get('status') == 'running'),
    }
