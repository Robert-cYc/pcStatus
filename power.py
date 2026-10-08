import os
import urllib.request
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

LHM_URL_ENV = "LHM_URL"
HTTP_TIMEOUT_SEC = 2

def _collect_lhm_powers(node: dict[str, Any], out: list[tuple[str, float]]) -> None:
    children = node.get("Children") or []
    if not children:
        value = node.get("Value")
        if isinstance(value, str) and "W" in value:
            try:
                w = float(value.replace("W", "").replace(",", ".").strip())
                out.append((str(node.get("Text", "")), w))
            except ValueError:
                pass
        return
    for child in children:
        _collect_lhm_powers(child, out)

class SystemPowerReader:
    def __init__(self, lhm_url: Optional[str] = None):
        self.lhm_url = lhm_url if lhm_url is not None else os.environ.get(LHM_URL_ENV, "http://localhost:8085/data.json")

    def read(self) -> Optional[float]:
        if not self.lhm_url:
            return None
        try:
            with urllib.request.urlopen(self.lhm_url, timeout=HTTP_TIMEOUT_SEC) as resp:
                root = json.load(resp)
                powers: list[tuple[str, float]] = []
                _collect_lhm_powers(root, powers)
                for wanted in ("cpu package", "package"):
                    for name, w in powers:
                        if name.lower() == wanted:
                            return w
                return max([w for n, w in powers]) if powers else None
        except Exception as exc:
            logger.debug("LibreHardwareMonitor power read failed: %s", exc)
            return None
