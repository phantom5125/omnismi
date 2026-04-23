"""Curated machine-profile metadata for CLI validation workflows."""

from __future__ import annotations

from dataclasses import dataclass
import re

from omnismi.models import VendorName

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class MachineProfile:
    """A small curated hardware-profile record used by the CLI."""

    name: str
    vendor: VendorName
    aliases: tuple[str, ...]
    description: str
    memory_total_bytes: int | None = None
    memory_class: str | None = None
    bandwidth_class: str | None = None


_PROFILES: dict[str, MachineProfile] = {
    "h100-pcie-80gb": MachineProfile(
        name="h100-pcie-80gb",
        vendor="nvidia",
        aliases=(
            "nvidia h100 pcie",
            "nvidia h100 80g",
            "h100 pcie",
            "h100 80gb",
        ),
        description="NVIDIA H100 PCIe 80GB class accelerator.",
        memory_total_bytes=80 * 1024**3,
        memory_class="hbm3",
        bandwidth_class="h100-pcie-class",
    ),
    "mi300x-192gb": MachineProfile(
        name="mi300x-192gb",
        vendor="amd",
        aliases=(
            "amd mi300x",
            "mi300x 192g",
            "mi300x 192gb",
            "instinct mi300x",
        ),
        description="AMD Instinct MI300X 192GB class accelerator.",
        memory_total_bytes=192 * 1024**3,
        memory_class="hbm3",
        bandwidth_class="mi300x-class",
    ),
    "tpu-v5p-32gb": MachineProfile(
        name="tpu-v5p-32gb",
        vendor="google",
        aliases=(
            "tpu v5p",
            "v5p",
            "tpu v5p chip",
        ),
        description="Google TPU v5p chip with 32GB HBM class capacity.",
        memory_total_bytes=32 * 1024**3,
        memory_class="hbm",
        bandwidth_class="tpu-v5p-class",
    ),
}


def list_profiles() -> tuple[MachineProfile, ...]:
    """Return all built-in machine profiles in stable name order."""

    return tuple(_PROFILES[name] for name in sorted(_PROFILES))


def get_profile(name: str) -> MachineProfile | None:
    """Return a profile by its canonical CLI name."""

    return _PROFILES.get(name)


def profile_to_dict(profile: MachineProfile) -> dict[str, object]:
    """Convert a profile into a structured-report object."""

    return {
        "name": profile.name,
        "vendor": profile.vendor,
        "aliases": list(profile.aliases),
        "description": profile.description,
        "memory_total_bytes": profile.memory_total_bytes,
        "memory_class": profile.memory_class,
        "bandwidth_class": profile.bandwidth_class,
    }


def profile_matches_device_name(profile: MachineProfile, device_name: str | None) -> bool:
    """Return whether a device name resembles one of the profile aliases."""

    if not device_name:
        return False

    normalized_name = _normalize(device_name)
    return any(_normalize(alias) in normalized_name for alias in profile.aliases)


def _normalize(value: str) -> str:
    return _NORMALIZE_RE.sub("", value.lower())
