import os
import urllib.request
import json
import logging
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)

LHM_URL_ENV = "LHM_URL"
HTTP_TIMEOUT_SEC = 2

def _walk_lhm(node: dict[str, Any], results: list[dict]) -> None:
    children = node.get("Children") or []
    if not children:
        text = node.get("Text", "")
        value = node.get("Value", "")
        if isinstance(value, str):
            try:
                if "MHz" in value:
                    val = float(value.replace("MHz", "").replace(",", ".").strip())
                    results.append({"type": "clock", "name": text, "value": val})
                elif "RPM" in value:
                    val = float(value.replace("RPM", "").replace(",", ".").strip())
                    results.append({"type": "fan", "name": text, "value": val})
            except ValueError:
                pass
        return
    for child in children:
        _walk_lhm(child, results)

class LhmSensorReader:
    def __init__(self, lhm_url: Optional[str] = None):
        self.lhm_url = lhm_url if lhm_url is not None else os.environ.get(LHM_URL_ENV, "http://localhost:8085/data.json")

    def read(self) -> Dict[str, Optional[float]]:
        stats: Dict[str, Optional[float]] = {
            "cpu_mhz": None,
            "gpu_mhz": None,
            "cpu_fan_rpm": None,
            "gpu_fan_rpm": None
        }
        if not self.lhm_url:
            return stats
        
        try:
            with urllib.request.urlopen(self.lhm_url, timeout=HTTP_TIMEOUT_SEC) as resp:
                root = json.load(resp)
                results: list[dict] = []
                _walk_lhm(root, results)
                
                cpu_clocks = [r["value"] for r in results if r["type"] == "clock" and "CPU" in r["name"].upper()]
                if not cpu_clocks:
                    cpu_clocks = [r["value"] for r in results if r["type"] == "clock" and "Core" in r["name"]]
                if cpu_clocks:
                    stats["cpu_mhz"] = max(cpu_clocks)
                    
                gpu_clocks = [r["value"] for r in results if r["type"] == "clock" and "GPU" in r["name"].upper()]
                if gpu_clocks:
                    stats["gpu_mhz"] = max(gpu_clocks)
                    
                cpu_fans = [r["value"] for r in results if r["type"] == "fan" and ("CPU" in r["name"].upper() or "FAN #1" in r["name"].upper() or "FAN 1" in r["name"].upper())]
                all_fans = [r["value"] for r in results if r["type"] == "fan"]
                if cpu_fans:
                    stats["cpu_fan_rpm"] = max(cpu_fans)
                elif all_fans:
                    stats["cpu_fan_rpm"] = max(all_fans)
                    
                gpu_fans = [r["value"] for r in results if r["type"] == "fan" and "GPU" in r["name"].upper()]
                if gpu_fans:
                    stats["gpu_fan_rpm"] = max(gpu_fans)
                    
                return stats
        except Exception as exc:
            logger.debug("LibreHardwareMonitor sensors read failed: %s", exc)
            return stats
