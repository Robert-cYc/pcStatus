"""System data collectors built on psutil."""

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import psutil

from temperature import TemperatureReader

logger = logging.getLogger(__name__)

GB = 1024 ** 3
DEFAULT_PROCESS_LIMIT = 8


@dataclass(frozen=True)
class Snapshot:
    ts: int
    cpu: float
    cores: list[float]
    memory: float
    mem_used_gb: float
    mem_total_gb: float
    disks: list[dict[str, Any]]
    net_sent: int
    net_recv: int
    temp_c: Optional[float]
    temp_source: Optional[str]
    gpu: Optional[dict[str, Any]] = None



def collect_disks() -> list[dict[str, Any]]:
    """Usage of every real mounted partition (duplicates sharing one volume are collapsed)."""
    disks: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for part in psutil.disk_partitions(all=False):
        if "cdrom" in part.opts or not part.fstype:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except OSError as exc:  # unreadable drive, e.g. empty card reader or permission denied
            logger.debug("Skipping partition %s: %s", part.mountpoint, exc)
            continue
        fingerprint = (usage.total, usage.used)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        disks.append({
            "mount": part.mountpoint,
            "percent": round(usage.percent, 1),
            "used_gb": round(usage.used / GB, 1),
            "total_gb": round(usage.total / GB, 1),
        })
    return disks


def collect_top_processes(limit: int = DEFAULT_PROCESS_LIMIT) -> list[dict[str, Any]]:
    """Top processes by CPU share (normalized to 0-100% of the whole machine)."""
    cpu_count = psutil.cpu_count() or 1
    processes: list[dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        info = proc.info
        if info.get("pid") == 0:  # System Idle Process
            continue
        processes.append({
            "pid": info["pid"],
            "name": info.get("name") or "?",
            "cpu": round((info.get("cpu_percent") or 0.0) / cpu_count, 1),
            "memory": round(info.get("memory_percent") or 0.0, 1),
        })
    processes.sort(key=lambda p: (p["cpu"], p["memory"]), reverse=True)
    return processes[:limit]


def collect_snapshot(temp_reader: TemperatureReader, gpu_monitor: Optional[Any] = None) -> Snapshot:
    """Gather one consistent reading (blocks ~1s to measure CPU)."""
    cores = psutil.cpu_percent(interval=1, percpu=True)
    cpu = sum(cores) / len(cores) if cores else 0.0
    memory = psutil.virtual_memory()
    net = psutil.net_io_counters()
    temp = temp_reader.read()
    return Snapshot(
        ts=int(time.time()),
        cpu=cpu,
        cores=[round(c, 1) for c in cores],
        memory=memory.percent,
        mem_used_gb=memory.used / GB,
        mem_total_gb=memory.total / GB,
        disks=collect_disks(),
        net_sent=net.bytes_sent,
        net_recv=net.bytes_recv,
        temp_c=temp[0] if temp else None,
        temp_source=temp[1] if temp else None,
        gpu=gpu_monitor.read() if gpu_monitor else None,
    )
