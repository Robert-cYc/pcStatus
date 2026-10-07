import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False


class GPUMonitor:
    def __init__(self):
        self.enabled = False
        self.handle = None
        self.name = None
        if NVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                # handle bytes returning from pynvml
                name_bytes = pynvml.nvmlDeviceGetName(self.handle)
                self.name = name_bytes.decode() if isinstance(name_bytes, bytes) else name_bytes
                self.enabled = True
                logger.info(f"GPU Monitor initialized: {self.name}")
            except Exception as e:
                logger.warning(f"Failed to initialize NVML: {e}")

    def read(self) -> Optional[dict]:
        if not self.enabled:
            return None
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(self.handle)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self.handle)
            temp = pynvml.nvmlDeviceGetTemperature(self.handle, pynvml.NVML_TEMPERATURE_GPU)
            
            return {
                "name": self.name,
                "gpu_percent": util.gpu,
                "memory_percent": round((mem_info.used / mem_info.total) * 100, 1) if mem_info.total > 0 else 0,
                "memory_used_gb": round(mem_info.used / (1024**3), 2),
                "memory_total_gb": round(mem_info.total / (1024**3), 2),
                "temp_c": temp
            }
        except Exception as e:
            logger.debug(f"Failed to read GPU stats: {e}")
            return None

    def close(self):
        if self.enabled:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
