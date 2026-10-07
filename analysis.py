"""Pure functions: anomaly detection and display-stat formatting."""

from datetime import datetime
from typing import Mapping, Optional

from collectors import Snapshot

WARN_MARK = "⚠️"
TEMP_LABEL = "CPU 溫度"
TEMP_UNAVAILABLE_TEXT = "未偵測到感測器"


def format_rate(bytes_per_sec: float) -> str:
    if bytes_per_sec >= 1024 ** 2:
        return f"{bytes_per_sec / 1024 ** 2:.2f} MB/s"
    if bytes_per_sec >= 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    return f"{bytes_per_sec:.0f} B/s"


def _max_disk_percent(snapshot: Snapshot) -> float:
    return max((d["percent"] for d in snapshot.disks), default=0.0)


def detect_anomalies(snapshot: Snapshot, thresholds: Mapping[str, float]) -> list[str]:
    """Messages are value-free so they stay stable (used as notification cooldown keys)."""
    anomalies: list[str] = []
    if snapshot.cpu > thresholds["cpu_percent"]:
        anomalies.append(f"CPU 使用率超過 {thresholds['cpu_percent']:g}% 閥值")
    if snapshot.memory > thresholds["memory_percent"]:
        anomalies.append(f"記憶體使用率超過 {thresholds['memory_percent']:g}% 閥值")
    for disk in snapshot.disks:
        if disk["percent"] > thresholds["disk_percent"]:
            anomalies.append(f"磁碟 {disk['mount']} 使用率超過 {thresholds['disk_percent']:g}% 閥值")
    if snapshot.temp_c is not None and snapshot.temp_c > thresholds["temp_celsius"]:
        anomalies.append(f"CPU 溫度超過 {thresholds['temp_celsius']:g}°C 閥值")
    return anomalies


def _flag(text: str, exceeded: bool) -> str:
    return f"{text} {WARN_MARK}" if exceeded else text


def build_stats(
    snapshot: Snapshot,
    thresholds: Mapping[str, float],
    sent_bps: float,
    recv_bps: float,
    boot_time: str,
    now: Optional[datetime] = None,
) -> dict[str, str]:
    """Display dictionary consumed by the dashboard (keys are UI labels)."""
    now = now or datetime.now()
    disk_pct = _max_disk_percent(snapshot)
    temp_text = (
        _flag(f"{snapshot.temp_c:.1f}°C", snapshot.temp_c > thresholds["temp_celsius"])
        if snapshot.temp_c is not None else TEMP_UNAVAILABLE_TEXT
    )
    return {
        "CPU 使用率": _flag(f"{snapshot.cpu:.1f}%", snapshot.cpu > thresholds["cpu_percent"]),
        "記憶體使用率": _flag(f"{snapshot.memory:.1f}%", snapshot.memory > thresholds["memory_percent"]),
        "硬碟使用率": _flag(f"{disk_pct:.1f}%", disk_pct > thresholds["disk_percent"]),
        TEMP_LABEL: temp_text,
        "記憶體總量": f"{snapshot.mem_total_gb:.1f} GB",
        "已用記憶體": f"{snapshot.mem_used_gb:.1f} GB",
        "網路發送速率": format_rate(sent_bps),
        "網路接收速率": format_rate(recv_bps),
        "開機時間": boot_time,
        "當前時間": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
