from datetime import datetime

from analysis import build_stats, detect_anomalies, format_rate
from collectors import Snapshot
from config import DEFAULT_THRESHOLDS


def make_snapshot(**overrides) -> Snapshot:
    base = dict(
        ts=0, cpu=10.0, cores=[10.0, 10.0], memory=40.0, mem_used_gb=4.0, mem_total_gb=16.0,
        disks=[{"mount": "C:\\", "percent": 50.0, "used_gb": 100.0, "total_gb": 200.0}],
        net_sent=0, net_recv=0, temp_c=50.0, temp_source="test",
    )
    base.update(overrides)
    return Snapshot(**base)


def test_no_anomalies() -> None:
    assert detect_anomalies(make_snapshot(), DEFAULT_THRESHOLDS) == []


def test_all_anomalies_detected() -> None:
    snap = make_snapshot(
        cpu=95.0, memory=95.0, temp_c=90.0,
        disks=[{"mount": "D:\\", "percent": 99.0, "used_gb": 1.0, "total_gb": 1.0}],
    )
    messages = detect_anomalies(snap, DEFAULT_THRESHOLDS)
    assert len(messages) == 4
    assert any("D:\\" in m for m in messages)
    assert any("°C" in m for m in messages)


def test_missing_temperature_is_not_anomaly() -> None:
    snap = make_snapshot(temp_c=None, temp_source=None)
    assert detect_anomalies(snap, DEFAULT_THRESHOLDS) == []
    stats = build_stats(snap, DEFAULT_THRESHOLDS, 0, 0, "boot")
    assert stats["CPU 溫度"] == "未偵測到感測器"


def test_build_stats_flags_exceeded_values() -> None:
    stats = build_stats(make_snapshot(cpu=99.0), DEFAULT_THRESHOLDS, 0, 0, "boot", now=datetime(2026, 1, 1))
    assert "⚠️" in stats["CPU 使用率"]
    assert "⚠️" not in stats["記憶體使用率"]
    assert stats["當前時間"] == "2026-01-01 00:00:00"


def test_format_rate_units() -> None:
    assert format_rate(500) == "500 B/s"
    assert format_rate(2048) == "2.0 KB/s"
    assert format_rate(3 * 1024 ** 2) == "3.00 MB/s"
