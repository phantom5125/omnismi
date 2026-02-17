"""Base vendor interface for GPU implementations."""

from abc import ABC, abstractmethod
from typing import List, Optional

from omnismi.types import GPUInfo, GPUMetrics


class BaseVendor(ABC):
    """Abstract base class for GPU vendor implementations."""

    name: str  # Vendor name (e.g., "nvidia", "amd")

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this vendor's GPUs are available on the system."""
        ...

    @abstractmethod
    def list_gpus(self) -> List[GPUInfo]:
        """List all GPUs from this vendor."""
        ...

    @abstractmethod
    def get_metrics(self, gpu_id: int) -> Optional[GPUMetrics]:
        """Get current metrics for a specific GPU."""
        ...

    @abstractmethod
    def get_info(self, gpu_id: int) -> Optional[GPUInfo]:
        """Get static information for a specific GPU."""
        ...
