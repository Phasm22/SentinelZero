"""System metrics collector — cpu, memory, disk, load, uptime."""
import os
import time

import psutil


def collect_system() -> dict:
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    load = os.getloadavg()

    disk = {}
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disk[part.mountpoint] = {
                'pct': usage.percent,
                'free_gb': round(usage.free / 1_073_741_824, 1),
                'total_gb': round(usage.total / 1_073_741_824, 1),
            }
        except (PermissionError, OSError):
            pass

    return {
        'cpu_pct': cpu,
        'mem_pct': mem.percent,
        'mem_total_gb': round(mem.total / 1_073_741_824, 1),
        'mem_used_gb': round(mem.used / 1_073_741_824, 1),
        'load_avg': [round(x, 2) for x in load],
        'uptime_s': int(time.time() - psutil.boot_time()),
        'disk': disk,
    }
