"""Convert stored metric rows into chart-ready series (pure functions)."""

import math
from datetime import datetime
from typing import Any, Optional, Sequence

from storage import MetricRow

MAX_GAP_SEC = 300  # longer gaps (app was down) produce no rate instead of a misleading average


def compute_rate_kbps(prev_ts: int, ts: int, prev_bytes: int, bytes_now: int) -> Optional[float]:
    """KB/s between two cumulative counters; ``None`` for gaps, resets or bad timestamps."""
    elapsed = ts - prev_ts
    delta = bytes_now - prev_bytes
    if elapsed <= 0 or elapsed > MAX_GAP_SEC or delta < 0:
        return None
    return delta / elapsed / 1024


def downsample(rows: Sequence[Any], max_points: int) -> list[Any]:
    """Keep at most ``max_points`` evenly spaced items, always including the newest."""
    if max_points < 1:
        raise ValueError("max_points must be >= 1")
    if len(rows) <= max_points:
        return list(rows)
    step = math.ceil(len(rows) / max_points)
    return list(rows[::-1][::step][::-1])


def label_format(minutes: int) -> str:
    if minutes <= 60:
        return "%H:%M:%S"
    if minutes <= 360:
        return "%H:%M"
    return "%m-%d %H:%M"


def build_history(rows: Sequence[MetricRow], minutes: int, max_points: int = 240) -> dict[str, list]:
    """Build series dict; network rates are computed before downsampling."""
    rates: list[tuple[Optional[float], Optional[float]]] = [(None, None)]
    for prev, cur in zip(rows, rows[1:]):
        rates.append((
            compute_rate_kbps(prev[0], cur[0], prev[5], cur[5]),
            compute_rate_kbps(prev[0], cur[0], prev[6], cur[6]),
        ))
    if not rows:
        rates = []

    combined = downsample(list(zip(rows, rates)), max_points)
    fmt = label_format(minutes)
    history: dict[str, list] = {
        "timestamps": [], "cpu": [], "memory": [], "disk": [], "temp": [],
        "net_sent_kbps": [], "net_recv_kbps": [],
    }
    for (ts, cpu, memory, disk, temp, _sent, _recv), (sent_rate, recv_rate) in combined:
        history["timestamps"].append(datetime.fromtimestamp(ts).strftime(fmt))
        history["cpu"].append(round(cpu, 1))
        history["memory"].append(round(memory, 1))
        history["disk"].append(round(disk, 1))
        history["temp"].append(round(temp, 1) if temp is not None else None)
        history["net_sent_kbps"].append(round(sent_rate, 1) if sent_rate is not None else None)
        history["net_recv_kbps"].append(round(recv_rate, 1) if recv_rate is not None else None)
    return history
