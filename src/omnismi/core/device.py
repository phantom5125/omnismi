"""GPU device abstraction."""

from typing import Optional

from omnismi.types import GPUInfo, GPUMetrics
from omnismi.vendors import get_vendors


class GPUDevice:
    """Represents a single GPU device."""

    def __init__(self, info: GPUInfo, vendor_name: str):
        self._info = info
        self._vendor_name = vendor_name

    @property
    def id(self) -> int:
        """GPU ID."""
        return self._info.id

    @property
    def name(self) -> str:
        """GPU name."""
        return self._info.name

    @property
    def vendor(self) -> str:
        """GPU vendor."""
        return self._info.vendor

    @property
    def memory_total(self) -> Optional[int]:
        """Total GPU memory in bytes."""
        return self._info.memory_total

    @property
    def driver_version(self) -> Optional[str]:
        """GPU driver version."""
        return self._info.driver_version

    def get_metrics(self) -> Optional[GPUMetrics]:
        """Get current metrics for this GPU."""
        for vendor in get_vendors():
            if vendor.name == self._vendor_name:
                return vendor.get_metrics(self._info.id)
        return None

    def get_info(self) -> GPUInfo:
        """Get static information for this GPU."""
        return self._info

    def __repr__(self) -> str:
        return f"GPUDevice(id={self.id}, name={self.name}, vendor={self.vendor})"


def get_gpu(gpu_id: int) -> Optional[GPUDevice]:
    """Get a GPU device by its ID.

    Args:
        gpu_id: The global GPU ID.

    Returns:
        GPUDevice if found, None otherwise.
    """
    from omnismi.core.detector import detect_gpus

    gpus = detect_gpus()
    if gpu_id < len(gpus):
        info = gpus[gpu_id]
        return GPUDevice(info, info.vendor)
    return None


def list_gpus() -> list[GPUDevice]:
    """List all available GPU devices.

    Returns:
        List of GPUDevice objects.
    """
    from omnismi.core.detector import detect_gpus

    gpus = detect_gpus()
    return [GPUDevice(info, info.vendor) for info in gpus]
