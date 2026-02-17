"""NVIDIA GPU support via pynvml."""

from typing import List, Optional

from omnismi.imports import get_pynvml, is_pynvml_available
from omnismi.types import GPUInfo, GPUMetrics
from omnismi.vendors.base import BaseVendor


# pynvml API version compatibility mapping
# Some APIs were added/removed between versions
NVML_API_VERSION = {
    # NVML_API_VERSION_11_5 (pynvml 11.5+)
    "nvmlDeviceGetPowerUsage": "11.0",
    "nvmlDeviceGetClockInfo": "11.0",
    "nvmlDeviceGetUtilizationRates": "11.0",
    "nvmlDeviceGetMemoryInfo": "11.0",
    "nvmlDeviceGetTemperature": "11.0",
    "nvmlDeviceGetName": "11.0",
    "nvmlDeviceGetHandleByIndex": "11.0",
    "nvmlDeviceGetCount": "11.0",
    "nvmlSystemGetDriverVersion": "11.0",
}

# Known API changes between CUDA versions
CUDA_API_COMPATIBILITY = {
    # CUDA 11.x
    "11.x": {
        "available": True,
        "notes": "Full API support",
    },
    # CUDA 12.x
    "12.x": {
        "available": True,
        "notes": "Same API, more metrics available",
    },
}


class NVIDIAVendor(BaseVendor):
    """NVIDIA GPU vendor implementation."""

    name = "nvidia"

    def __init__(self):
        self._initialized = False
        self._nvml = None

    def _ensure_init(self) -> bool:
        """Initialize pynvml if not already done."""
        if not is_pynvml_available():
            return False
        if self._initialized:
            return True

        try:
            self._nvml = get_pynvml()
            self._nvml.nvmlInit()
            self._initialized = True
            return True
        except Exception:
            return False

    def is_available(self) -> bool:
        """Check if NVIDIA GPUs are available."""
        if not self._ensure_init():
            return False
        try:
            count = self._nvml.nvmlDeviceGetCount()
            return count > 0
        except Exception:
            return False

    def list_gpus(self) -> List[GPUInfo]:
        """List all NVIDIA GPUs."""
        if not self._ensure_init():
            return []
        try:
            count = self._nvml.nvmlDeviceGetCount()
            gpus = []
            for i in range(count):
                handle = self._nvml.nvmlDeviceGetHandleByIndex(i)
                name = self._nvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")

                memory_info = None
                try:
                    mem_info = self._nvml.nvmlDeviceGetMemoryInfo(handle)
                    memory_info = mem_info.total
                except Exception:
                    pass

                driver_version = None
                try:
                    driver_version = self._nvml.nvmlSystemGetDriverVersion()
                except Exception:
                    pass

                gpus.append(
                    GPUInfo(
                        id=i,
                        name=name,
                        vendor=self.name,
                        driver_version=driver_version,
                        memory_total=memory_info,
                    )
                )
            return gpus
        except Exception:
            return []

    def get_info(self, gpu_id: int) -> Optional[GPUInfo]:
        """Get information for a specific NVIDIA GPU."""
        gpus = self.list_gpus()
        for gpu in gpus:
            if gpu.id == gpu_id:
                return gpu
        return None

    def get_metrics(self, gpu_id: int) -> Optional[GPUMetrics]:
        """Get current metrics for a specific NVIDIA GPU."""
        if not self._ensure_init():
            return None

        try:
            handle = self._nvml.nvmlDeviceGetHandleByIndex(gpu_id)

            # Memory
            memory_used = None
            memory_free = None
            try:
                mem_info = self._nvml.nvmlDeviceGetMemoryInfo(handle)
                memory_used = mem_info.used
                memory_free = mem_info.free
            except Exception:
                pass

            # Utilization
            utilization_gpu = None
            utilization_memory = None
            try:
                util = self._nvml.nvmlDeviceGetUtilizationRates(handle)
                utilization_gpu = util.gpu
                utilization_memory = util.memory
            except Exception:
                pass

            # Temperature
            temperature = None
            try:
                temperature = self._nvml.nvmlDeviceGetTemperature(
                    handle, self._nvml.NVML_TEMPERATURE_GPU
                )
            except Exception:
                pass

            # Power
            power_usage = None
            try:
                power_usage = self._nvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # mW to W
            except Exception:
                pass

            # Clock speed
            clock_speed = None
            try:
                clock_speed = self._nvml.nvmlDeviceGetClockInfo(
                    handle, self._nvml.NVML_CLOCK_SM
                )
            except Exception:
                pass

            return GPUMetrics(
                id=gpu_id,
                memory_used=memory_used,
                memory_free=memory_free,
                utilization_gpu=utilization_gpu,
                utilization_memory=utilization_memory,
                temperature=temperature,
                power_usage=power_usage,
                clock_speed=clock_speed,
            )
        except Exception:
            return None


# Backward compatibility alias
NVIDIAVendorGPU = NVIDIAVendor
