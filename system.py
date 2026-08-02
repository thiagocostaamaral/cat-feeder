import time
import os


def _read_cpu():
    with open("/proc/stat") as f:
        fields = f.readline().split()[1:]
    return sum(int(v) for v in fields), int(fields[3])


def _cpu_percent():
    total1, idle1 = _read_cpu()
    time.sleep(0.1)
    total2, idle2 = _read_cpu()

    total_delta = total2 - total1
    idle_delta = idle2 - idle1

    if total_delta == 0:
        return 0.0

    return round(100 * (1 - idle_delta / total_delta), 1)


def _ram():
    with open("/proc/meminfo") as f:
        lines = f.readlines()

    total = int(lines[0].split()[1])
    available = int(lines[2].split()[1])
    used = total - available

    return {
        "total_mb": round(total / 1024),
        "used_mb": round(used / 1024),
        "percent": round(100 * used / total, 1)
    }


def _temperature():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            millicelsius = int(f.read().strip())
        return round(millicelsius / 1000, 1)
    except Exception:
        return None


def _uptime():
    with open("/proc/uptime") as f:
        seconds = float(f.readline().split()[0])

    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)

    return f"{days}d {hours}h {minutes}m"


def get_stats():
    return {
        "cpu_percent": _cpu_percent(),
        "ram": _ram(),
        "temperature_c": _temperature(),
        "uptime": _uptime(),
        "time": time.strftime("%H:%M:%S")
    }
