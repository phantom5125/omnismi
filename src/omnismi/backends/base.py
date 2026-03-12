"""Base backend contract for vendor-specific accelerator implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from omnismi.models import GPUMetrics, GPUInfo, VendorName


class BaseBackend(ABC):
    """Abstract interface implemented by all accelerator vendor backends."""

    vendor: VendorName

    @abstractmethod
    def available(self) -> bool:
        """Return whether this backend can query devices on the host."""

    @abstractmethod
    def devices(self) -> list[Any]:
        """Return backend-local device handles."""

    @abstractmethod
    def info(self, device: Any, index: int) -> GPUInfo:
        """Return normalized static info for a single device."""

    @abstractmethod
    def metrics(self, device: Any, index: int) -> GPUMetrics:
        """Return normalized dynamic metrics for a single device."""

    def close(self) -> None:
        """Release backend resources."""
        return None
