"""Backend implementations for supported accelerator vendors."""

from omnismi.backends.amd import AmdBackend
from omnismi.backends.base import BaseBackend
from omnismi.backends.google_tpu import GoogleTpuBackend
from omnismi.backends.nvidia import NvidiaBackend
from omnismi.backends.registry import active_backends, close_all, registered_backends

__all__ = [
    "AmdBackend",
    "BaseBackend",
    "GoogleTpuBackend",
    "NvidiaBackend",
    "active_backends",
    "registered_backends",
    "close_all",
]
