"""CPU temperature readers with graceful fallbacks.

Source priority:
1. ``psutil.sensors_temperatures()`` (Linux / FreeBSD).
2. LibreHardwareMonitor / OpenHardwareMonitor remote web server
   (set env var ``LHM_URL``, e.g. ``http://localhost:8085/data.json``).
3. Windows ACPI thermal zone via WMI (often unavailable; may need admin).

If no source works, ``TemperatureReader.read()`` returns ``None``.
"""

import logging
import os
import re
import subprocess
import sys
import urllib.request
import json
from typing import Any, Optional

import psutil

logger = logging.getLogger(__name__)

LHM_URL_ENV = "LHM_URL"
HTTP_TIMEOUT_SEC = 2
POWERSHELL_TIMEOUT_SEC = 5
MIN_VALID_CELSIUS = 0.0
MAX_VALID_CELSIUS = 150.0

# Lower index = higher priority.
_PSUTIL_CHIP_PRIORITY = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "cpu-thermal", "acpitz")
_PREFERRED_LABELS = ("package", "tctl", "tdie", "cpu")
_LHM_PREFERRED_NAMES = ("cpu package", "core (tctl/tdie)", "tctl", "tdie", "core max", "cpu total")

_ACPI_COMMAND = (
    "Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
    "-ErrorAction Stop | Select-Object -ExpandProperty CurrentTemperature"
)


def _is_valid(celsius: float) -> bool:
    return MIN_VALID_CELSIUS < celsius < MAX_VALID_CELSIUS


def pick_psutil_temp(sensors: dict[str, list[Any]]) -> Optional[float]:
    """Choose a representative CPU temperature from ``psutil.sensors_temperatures()`` output."""
    if not sensors:
        return None

    ordered_chips = sorted(
        sensors,
        key=lambda chip: _PSUTIL_CHIP_PRIORITY.index(chip) if chip in _PSUTIL_CHIP_PRIORITY else len(_PSUTIL_CHIP_PRIORITY),
    )
    for chip in ordered_chips:
        entries = [e for e in sensors[chip] if e.current is not None and _is_valid(e.current)]
        if not entries:
            continue
        preferred = [e for e in entries if any(k in (e.label or "").lower() for k in _PREFERRED_LABELS)]
        return float(max((preferred or entries), key=lambda e: e.current).current)
    return None


def _parse_celsius(text: str) -> Optional[float]:
    """Parse strings like ``"45.0 °C"`` or ``"45,0 °C"`` (locale decimal comma)."""
    match = re.search(r"(-?\d+(?:[.,]\d+)?)\s*°?\s*C", text)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _collect_lhm_sensors(node: dict[str, Any], out: list[tuple[str, float]]) -> None:
    children = node.get("Children") or []
    if not children:
        value = node.get("Value")
        if isinstance(value, str) and "C" in value:
            celsius = _parse_celsius(value)
            if celsius is not None and _is_valid(celsius):
                out.append((str(node.get("Text", "")), celsius))
        return
    for child in children:
        _collect_lhm_sensors(child, out)


def parse_lhm_tree(root: dict[str, Any]) -> Optional[float]:
    """Extract the CPU temperature from a LibreHardwareMonitor ``data.json`` tree."""
    sensors: list[tuple[str, float]] = []
    _collect_lhm_sensors(root, sensors)

    for wanted in _LHM_PREFERRED_NAMES:
        for name, celsius in sensors:
            if name.lower() == wanted:
                return celsius

    cpu_like = [c for n, c in sensors if ("cpu" in n.lower() or "core" in n.lower()) and "gpu" not in n.lower()]
    return max(cpu_like) if cpu_like else None


def parse_acpi_output(output: str) -> Optional[float]:
    """Convert WMI ``CurrentTemperature`` values (tenths of Kelvin) to the max Celsius reading."""
    readings: list[float] = []
    for line in output.splitlines():
        line = line.strip()
        if not line.isdigit():
            continue
        celsius = int(line) / 10.0 - 273.15
        if _is_valid(celsius):
            readings.append(celsius)
    return max(readings) if readings else None


class TemperatureReader:
    """Reads CPU temperature, remembering which sources are permanently unavailable."""

    def __init__(self, lhm_url: Optional[str] = None) -> None:
        self.lhm_url = lhm_url if lhm_url is not None else os.environ.get(LHM_URL_ENV, "http://localhost:8085/data.json")
        self._psutil_supported = hasattr(psutil, "sensors_temperatures")
        self._acpi_supported = sys.platform == "win32"

    def read(self) -> Optional[tuple[float, str]]:
        """Return ``(celsius, source_name)`` or ``None`` when no sensor is available."""
        for source_name, reader in (
            ("psutil", self._read_psutil),
            ("LibreHardwareMonitor", self._read_lhm),
            ("Windows ACPI", self._read_acpi),
        ):
            celsius = reader()
            if celsius is not None:
                return celsius, source_name
        return None

    def _read_psutil(self) -> Optional[float]:
        if not self._psutil_supported:
            return None
        try:
            return pick_psutil_temp(psutil.sensors_temperatures())
        except (OSError, RuntimeError) as exc:
            logger.warning("psutil temperature read failed, disabling: %s", exc)
            self._psutil_supported = False
            return None

    def _read_lhm(self) -> Optional[float]:
        if not self.lhm_url:
            return None
        try:
            with urllib.request.urlopen(self.lhm_url, timeout=HTTP_TIMEOUT_SEC) as resp:
                return parse_lhm_tree(json.load(resp))
        except (OSError, ValueError) as exc:  # URLError subclasses OSError; JSONDecodeError subclasses ValueError
            logger.warning("LibreHardwareMonitor read failed (%s): %s", self.lhm_url, exc)
            return None

    def _read_acpi(self) -> Optional[float]:
        if not self._acpi_supported:
            return None
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", _ACPI_COMMAND],
                capture_output=True, text=True, timeout=POWERSHELL_TIMEOUT_SEC, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("Windows ACPI temperature unavailable, disabling: %s", exc)
            self._acpi_supported = False
            return None

        celsius = parse_acpi_output(result.stdout)
        if celsius is None:
            logger.info("Windows ACPI thermal zone returned no data (may need admin or unsupported); disabling.")
            self._acpi_supported = False
        return celsius
