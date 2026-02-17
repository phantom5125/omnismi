"""GPU detection logic."""

from typing import List

from omnismi.imports import is_amdsmi_available, is_pynvml_available
from omnismi.types import GPUInfo
from omnismi.vendors import get_vendors, register_vendor


def _lazy_register_vendors():
    """Lazily register vendor implementations based on available dependencies."""
    # This is called on first use to avoid importing vendors until needed
    if is_pynvml_available():
        try:
            from omnismi.vendors.nvidia import NVIDIAVendor
            register_vendor(NVIDIAVendor())
        except Exception:
            pass

    if is_amdsmi_available():
        try:
            from omnismi.vendors.amd import AMDVendor
            register_vendor(AMDVendor())
        except Exception:
            pass


# Lazy initialization flag
_vendors_initialized = False


def _ensure_vendors_initialized():
    """Ensure vendors are registered."""
    global _vendors_initialized
    if not _vendors_initialized:
        _lazy_register_vendors()
        _vendors_initialized = True


def detect_gpus() -> List[GPUInfo]:
    """Detect all available GPUs on the system.

    Returns:
        List of GPUInfo objects for all detected GPUs.
    """
    _ensure_vendors_initialized()

    all_gpus = []

    for vendor in get_vendors():
        if not vendor.is_available():
            continue

        gpus = vendor.list_gpus()
        for gpu in gpus:
            # Adjust ID to be globally unique across vendors
            global_id = len(all_gpus)
            gpu.id = global_id
            all_gpus.append(gpu)

    return all_gpus


def get_available_vendors() -> List[str]:
    """Get list of available GPU vendors on the system.

    Returns:
        List of vendor names that have GPUs available.
    """
    _ensure_vendors_initialized()

    vendors = []
    for vendor in get_vendors():
        if vendor.is_available():
            vendors.append(vendor.name)
    return vendors
