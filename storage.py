"""SQLite persistence for metric history and user-edited thresholds."""

import json
import sqlite3
import threading
from typing import Optional

MetricRow = tuple[int, float, float, float, Optional[float], int, int, Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    ts INTEGER PRIMARY KEY,
    cpu REAL NOT NULL,
    memory REAL NOT NULL,
    disk REAL NOT NULL,
    temp REAL,
    net_sent INTEGER NOT NULL,
    net_recv INTEGER NOT NULL,
    gpu_power REAL,
    sys_power REAL,
    cpu_mhz REAL,
    gpu_mhz REAL,
    cpu_fan_rpm REAL,
    gpu_fan_rpm REAL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""
_THRESHOLDS_KEY = "thresholds"


class MetricsStore:
    """Thread-safe wrapper around a single SQLite connection."""

    def __init__(self, path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)
            for col in ["gpu_power", "sys_power", "cpu_mhz", "gpu_mhz", "cpu_fan_rpm", "gpu_fan_rpm"]:
                try:
                    self._conn.execute(f"ALTER TABLE metrics ADD COLUMN {col} REAL")
                except sqlite3.OperationalError:
                    pass

    def insert(self, row: MetricRow) -> None:
        with self._lock, self._conn:
            self._conn.execute("INSERT OR REPLACE INTO metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", row)

    def query(self, since_ts: int) -> list[MetricRow]:
        with self._lock:
            cursor = self._conn.execute(
                "SELECT ts, cpu, memory, disk, temp, net_sent, net_recv, gpu_power, sys_power, cpu_mhz, gpu_mhz, cpu_fan_rpm, gpu_fan_rpm FROM metrics WHERE ts >= ? ORDER BY ts",
                (since_ts,),
            )
            return cursor.fetchall()

    def prune(self, older_than_ts: int) -> int:
        """Delete rows older than the timestamp; return number removed."""
        with self._lock, self._conn:
            return self._conn.execute("DELETE FROM metrics WHERE ts < ?", (older_than_ts,)).rowcount

    def load_thresholds(self) -> dict[str, float]:
        with self._lock:
            row = self._conn.execute("SELECT value FROM settings WHERE key = ?", (_THRESHOLDS_KEY,)).fetchone()
        return json.loads(row[0]) if row else {}

    def save_thresholds(self, thresholds: dict[str, float]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (_THRESHOLDS_KEY, json.dumps(thresholds)),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
