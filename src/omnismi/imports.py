"""Lazy import utilities for optional dependencies."""

from __future__ import annotations

import warnings
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def lazy_import(
    module_name: str,
    package: str,
    required_for: str,
    install_cmd: str,
) -> Callable[[], Any]:
    """Create a lazy import function with helpful error messages.

    Args:
        module_name: The module to import (e.g., "pynvml")
        package: The package to install (e.g., "pynvml>=11.5.0")
        required_for: Description of what this module is required for
        install_cmd: Command to install the package

    Returns:
        A function that performs the lazy import.
    """
    _module: Any = None
    _imported = False

    def _do_import() -> Any:
        nonlocal _module, _imported
        if _imported:
            return _module

        try:
            _module = __import__(module_name)
            _imported = True
            return _module
        except ImportError as e:
            raise ImportError(
                f"{module_name} is required for {required_for}. "
                f"Install with: pip install {package}"
            ) from e

    return _do_import


def try_import(module_name: str) -> tuple[bool, Any]:
    """Try to import a module, returning (success, module).

    Args:
        module_name: Module to import

    Returns:
        Tuple of (import_success, module_or_None)
    """
    try:
        mod = __import__(module_name)
        return True, mod
    except ImportError:
        return False, None


# Lazy imports for vendor libraries
_pynvml = None
_amdsmi = None


def get_pynvml():
    """Lazy import pynvml."""
    global _pynvml
    if _pynvml is None:
        success, _pynvml = try_import("pynvml")
        if not success:
            raise ImportError(
                "pynvml is required for NVIDIA GPU support. "
                "Install with: pip install omnismi[nvidia]"
            )
    return _pynvml


def get_amdsmi():
    """Lazy import amdsmi."""
    global _amdsmi
    if _amdsmi is None:
        success, _amdsmi = try_import("amdsmi")
        if not success:
            raise ImportError(
                "amdsmi is required for AMD GPU support. "
                "Install with: pip install omnismi[amd]"
            )
    return _amdsmi


def is_pynvml_available() -> bool:
    """Check if pynvml is installed."""
    success, _ = try_import("pynvml")
    return success


def is_amdsmi_available() -> bool:
    """Check if amdsmi is installed."""
    success, _ = try_import("amdsmi")
    return success
