"""Auto-installation of vendor dependencies."""

from __future__ import annotations

import subprocess
import sys
from typing import Optional


def install_nvidia() -> bool:
    """Install NVIDIA dependencies (pynvml).

    Returns:
        True if installation successful, False otherwise.
    """
    return _pip_install("pynvml>=11.5.0")


def install_amd() -> bool:
    """Install AMD dependencies (amdsmi).

    Returns:
        True if installation successful, False otherwise.
    """
    return _pip_install("amdsmi>=1.0.0")


def install_auto() -> bool:
    """Auto-detect and install required dependencies based on available GPUs.

    Returns:
        True if any installation successful, False otherwise.
    """
    from omnismi import detection

    installed_any = False

    # Check for NVIDIA GPUs
    cuda_info = detection.detect_cuda()
    if cuda_info and cuda_info.device_count > 0:
        if _pip_install("pynvml>=11.5.0"):
            installed_any = True

    # Check for AMD GPUs with ROCm
    rocm_info = detection.detect_rocm()
    if rocm_info:
        if _pip_install("amdsmi>=1.0.0"):
            installed_any = True

    return installed_any


def install_all() -> bool:
    """Install all vendor dependencies.

    Returns:
        True if installation successful, False otherwise.
    """
    return _pip_install("pynvml>=11.5.0", "amdsmi>=1.0.0")


def _pip_install(*packages: str) -> bool:
    """Install packages using pip.

    Args:
        *packages: Package names with optional version specifiers.

    Returns:
        True if installation successful, False otherwise.
    """
    cmd = [sys.executable, "-m", "pip", "install", "-q"]
    cmd.extend(packages)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_installed() -> dict[str, bool]:
    """Check which vendor libraries are installed.

    Returns:
        Dictionary with vendor names as keys and installation status as values.
    """
    status = {
        "nvidia": _is_installed("pynvml"),
        "amd": _is_installed("amdsmi"),
    }
    return status


def _is_installed(package: str) -> bool:
    """Check if a package is installed."""
    try:
        __import__(package)
        return True
    except ImportError:
        return False


def suggest_installation() -> str:
    """Generate installation suggestion based on available hardware.

    Returns:
        Suggestion message for user.
    """
    from omnismi import detection

    suggestions = []

    # Check CUDA
    cuda_info = detection.detect_cuda()
    if cuda_info and cuda_info.device_count > 0:
        suggestions.append(
            f"NVIDIA GPUs detected ({cuda_info.device_count} GPU(s), "
            f"driver {cuda_info.driver_version})"
        )
        if not _is_installed("pynvml"):
            suggestions.append("  Install NVIDIA support: pip install omnismi[nvidia]")

    # Check ROCm
    rocm_info = detection.detect_rocm()
    if rocm_info:
        suggestions.append(
            f"AMD ROCm detected (driver {rocm_info.driver_version})"
        )
        if not _is_installed("amdsmi"):
            suggestions.append("  Install AMD support: pip install omnismi[amd]")

    if not suggestions:
        # No GPUs detected
        return (
            "No GPUs detected. Install omnismi with:\n"
            "  pip install omnismi[all]  # All GPU support\n"
            "  pip install omnismi[nvidia]  # NVIDIA only\n"
            "  pip install omnismi[amd]  # AMD only\n"
            "\n"
            "Or run 'omnismi-install' to auto-detect and install."
        )

    # Check what's already installed
    status = check_installed()
    if not status["nvidia"] and not status["amd"]:
        suggestions.append("\nTo install: pip install omnismi[all]")

    return "\n".join(suggestions)
