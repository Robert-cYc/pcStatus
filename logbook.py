"""Thread-safe log file with simple size-based rotation."""

import os
import threading
from collections import deque
from datetime import datetime
from typing import Any

MAX_LOG_BYTES = 5 * 1024 * 1024
TAIL_LINES = 200


class LogBook:
    def __init__(self, path: str, max_bytes: int = MAX_LOG_BYTES) -> None:
        self._path = path
        self._max_bytes = max_bytes
        self._lock = threading.Lock()

    def write(self, message: str, level: str = "INFO") -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{timestamp}  {message}"
        with self._lock:
            self._rotate_if_needed()
            with open(self._path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        print(f"[{level}] {line}")

    def _rotate_if_needed(self) -> None:
        if os.path.exists(self._path) and os.path.getsize(self._path) >= self._max_bytes:
            os.replace(self._path, self._path + ".1")

    def recent(self, limit: int = TAIL_LINES) -> list[dict[str, Any]]:
        if not os.path.exists(self._path):
            return []
        with self._lock, open(self._path, "r", encoding="utf-8") as handle:
            lines = list(deque(handle, maxlen=limit))
        logs: list[dict[str, Any]] = []
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            parts = raw.split("  ", 1)
            if len(parts) == 2:
                logs.append({"timestamp": parts[0], "message": parts[1]})
            else:
                logs.append({"timestamp": "", "message": raw})
        return logs
