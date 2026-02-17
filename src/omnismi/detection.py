"""Driver version detection and compatibility checking."""

from __future__ import annotations

import os
import re
import subprocess
import warnings
from dataclasses import dataclass
from typing import Optional


@dataclass
class CUDAInfo:
    """CUDA driver information."""

    driver_version: str
    cuda_version: Optional[str]  # e.g., "12.2"
    device_count: int


@dataclass
class ROCmInfo:
    """ROCm driver information."""

    driver_version: str
    rocmm_version: Optional[str]  # e.g., "6.0"
    hip_version: Optional[str]  # e.g., "6.0"


def detect_cuda() -> Optional[CUDAInfo]:
    """Detect CUDA driver version and CUDA toolkit version.

    Returns:
        CUDAInfo if NVIDIA driver is available, None otherwise.
    """
    try:
        # Try nvidia-smi first (most common)
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        driver_version = result.stdout.strip().split("\n")[0]

        # Try to get CUDA version from nvidia-smi
        cuda_version = None
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Parse compute capability to infer CUDA version
            # This is an approximation
            compute_cap = result.stdout.strip().split("\n")[0]
            cuda_version = _compute_cap_to_cuda_version(compute_cap)

        # Try nvcc for more accurate CUDA version
        cuda_version = _get_cuda_from_nvcc() or cuda_version

        # Get device count
        device_count = _get_nvidia_device_count()

        return CUDAInfo(
            driver_version=driver_version,
            cuda_version=cuda_version,
            device_count=device_count,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, IndexError):
        return None


def detect_rocm() -> Optional[ROCmInfo]:
    """Detect ROCm driver version and ROCm toolkit version.

    Returns:
        ROCmInfo if AMD GPU with ROCm is available, None otherwise.
    """
    try:
        # Try rocm-smi for driver version
        result = subprocess.run(
            ["rocm-smi", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None

        # Parse driver version from output
        driver_version = _parse_rocm_version(result.stderr or result.stdout)

        # Try to get ROCm/HIP version
        rocmm_version = _get_rocm_version()
        hip_version = _get_hip_version()

        # Get device count
        device_count = _get_amd_device_count()

        if device_count == 0:
            return None

        return ROCmInfo(
            driver_version=driver_version,
            rocmm_version=rocmm_version,
            hip_version=hip_version,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _get_nvidia_device_count() -> int:
    """Get number of NVIDIA GPUs."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--list-gpus"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
    except Exception:
        pass
    return 0


def _get_amd_device_count() -> int:
    """Get number of AMD GPUs with ROCm support."""
    try:
        result = subprocess.run(
            ["rocm-smi", "--list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split("\n") if l]
            return len(lines)
    except Exception:
        pass
    return 0


def _get_cuda_from_nvcc() -> Optional[str]:
    """Get CUDA version from nvcc."""
    try:
        result = subprocess.run(
            ["nvcc", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            match = re.search(r"release (\d+\.\d+)", result.stdout)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None


def _compute_cap_to_cuda_version(compute_cap: str) -> Optional[str]:
    """Map compute capability to approximate CUDA version."""
    mapping = {
        "8.0": "11.0",
        "8.6": "11.1",
        "8.7": "11.4",
        "8.9": "12.0",
        "9.0": "12.2",
    }
    return mapping.get(compute_cap)


def _parse_rocm_version(output: str) -> str:
    """Parse ROCm version from output."""
    # Example: rocm-smi version: 6.0.0-40594--6.0.0
    match = re.search(r"rocm-smi version:\s*(\d+\.\d+)", output)
    if match:
        return match.group(1)
    return "unknown"


def _get_rocm_version() -> Optional[str]:
    """Get ROCm version from /sys."""
    try:
        # ROCm 5.x uses this path
        with open("/sys/module/amdgpu/version", "r") as f:
            return f.read().strip()
    except Exception:
        pass

    # Try ROCm 6.x
    try:
        result = subprocess.run(
            ["ls", "/opt/rocm"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            versions = re.findall(r"(\d+\.\d+)", result.stdout)
            if versions:
                return versions[-1]  # Return highest version
    except Exception:
        pass

    return None


def _get_hip_version() -> Optional[str]:
    """Get HIP version."""
    try:
        result = subprocess.run(
            ["hipcc", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            match = re.search(r"HIP version\s*:\s*(\d+\.\d+)", result.stdout)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None


def check_cuda_compatibility(min_cuda_version: str = "11.0") -> tuple[bool, str]:
    """Check if CUDA version meets minimum requirement.

    Args:
        min_cuda_version: Minimum required CUDA version (e.g., "11.0")

    Returns:
        Tuple of (is_compatible, message)
    """
    cuda_info = detect_cuda()

    if cuda_info is None:
        return False, "NVIDIA driver not found"

    if cuda_info.cuda_version is None:
        return True, f"Driver {cuda_info.driver_version} installed (CUDA version unknown)"

    # Compare versions
    if _version_compare(cuda_info.cuda_version, min_cuda_version) >= 0:
        return True, f"CUDA {cuda_info.cuda_version} (driver {cuda_info.driver_version})"
    else:
        return False, f"CUDA {cuda_info.cuda_version} < required {min_cuda_version}"


def check_rocm_compatibility(min_rocmm_version: str = "5.0") -> tuple[bool, str]:
    """Check if ROCm version meets minimum requirement.

    Args:
        min_rocmm_version: Minimum required ROCm version (e.g., "5.0")

    Returns:
        Tuple of (is_compatible, message)
    """
    rocm_info = detect_rocm()

    if rocm_info is None:
        return False, "ROCm driver not found"

    if rocm_info.rocmm_version is None:
        return True, f"Driver {rocm_info.driver_version} installed (ROCm version unknown)"

    # Compare versions
    if _version_compare(rocm_info.rocmm_version, min_rocmm_version) >= 0:
        return True, f"ROCm {rocm_info.rocmm_version} (driver {rocm_info.driver_version})"
    else:
        return False, f"ROCm {rocm_info.rocmm_version} < required {min_rocmm_version}"


def _version_compare(v1: str, v2: str) -> int:
    """Compare two version strings.

    Returns:
        1 if v1 > v2, 0 if v1 == v2, -1 if v1 < v2
    """
    parts1 = [int(x) for x in v1.split(".")]
    parts2 = [int(x) for x in v2.split(".")]

    # Pad with zeros
    max_len = max(len(parts1), len(parts2))
    parts1.extend([0] * (max_len - len(parts1)))
    parts2.extend([0] * (max_len - len(parts2)))

    for p1, p2 in zip(parts1, parts2):
        if p1 > p2:
            return 1
        elif p1 < p2:
            return -1
    return 0
