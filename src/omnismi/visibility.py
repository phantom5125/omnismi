"""Parse accelerator visibility env vars and filter device lists."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field

_AMD_VISIBILITY_ENV_VARS = (
    "ROCR_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "GPU_DEVICE_ORDINAL",
)
_VISIBILITY_ENV_VARS = ("CUDA_VISIBLE_DEVICES", *_AMD_VISIBILITY_ENV_VARS)


@dataclass(frozen=True)
class VisibilityContext:
    """How devices were filtered for this snapshot."""

    mode: str
    env: dict[str, str]
    physical_indices: list[int]
    logical_indices: list[int]
    enforcement: str = "runtime_hint_only"
    warnings: list[str] = field(default_factory=list)


def _parse_visible_devices(raw: str) -> list[str]:
    value = raw.strip()
    if value == "":
        return []
    return [part.strip() for part in value.split(",")]


def parse_cuda_visible_devices(raw: str | None = None) -> list[str] | None:
    """Return CUDA_VISIBLE_DEVICES tokens, or None if unset."""
    if raw is None:
        if "CUDA_VISIBLE_DEVICES" not in os.environ:
            return None
        raw = os.environ["CUDA_VISIBLE_DEVICES"]
    return _parse_visible_devices(raw)


def _uuid_matches(token: str, uuid: str | None) -> bool:
    if not uuid:
        return False
    t = token.lower()
    u = uuid.lower()
    if t == u:
        return True
    return t.startswith("gpu-") and len(t) > 4 and u.startswith(t)


def _device_vendor(device: object) -> str:
    return str(getattr(device.info(), "vendor", "") or "").lower()


def _filter_by_tokens(
    devices: Sequence[object], tokens: list[str], *, allow_uuid: bool
) -> list[object]:
    if not tokens:
        return []

    by_index = {int(getattr(device, "index")): device for device in devices}
    selected: list[object] = []
    for token in tokens:
        if token.isdigit() or (token.startswith("-") and token[1:].isdigit()):
            device = by_index.get(int(token))
        elif allow_uuid:
            matches = [
                device
                for device in devices
                if _uuid_matches(token, getattr(device.info(), "uuid", None))
            ]
            device = matches[0] if len(matches) == 1 else None
        else:
            device = None
        if device is None or any(device is previous for previous in selected):
            break
        selected.append(device)
    return selected


def _context(
    selected: Sequence[object],
    env: dict[str, str],
    *,
    mode: str,
    warnings: list[str] | None = None,
) -> tuple[list[object], VisibilityContext]:
    physical = [int(getattr(device, "index")) for device in selected]
    return list(selected), VisibilityContext(
        mode=mode,
        env=env,
        physical_indices=physical,
        logical_indices=list(range(len(physical))),
        warnings=list(warnings or []),
    )


def filter_gpus_by_visibility(
    devices: Sequence[object],
    *,
    visible_only: bool = True,
    cuda_visible_devices: str | None = None,
) -> tuple[list[object], VisibilityContext]:
    """Filter devices using only environment controls applicable to their vendor."""
    env = {
        name: os.environ[name] for name in _VISIBILITY_ENV_VARS if name in os.environ
    }
    if not visible_only:
        return _context(devices, env, mode="all")

    nvidia: list[object] = []
    amd: list[object] = []
    other: list[object] = []
    for device in devices:
        vendor = _device_vendor(device)
        if vendor in {"", "nvidia"}:
            nvidia.append(device)
        elif vendor == "amd":
            amd.append(device)
        else:
            other.append(device)

    cuda_tokens = parse_cuda_visible_devices(cuda_visible_devices)
    selected_nvidia = (
        nvidia
        if cuda_tokens is None
        else _filter_by_tokens(nvidia, cuda_tokens, allow_uuid=True)
    )

    selected_amd = list(amd)
    active_amd_controls: list[str] = []
    for name in _AMD_VISIBILITY_ENV_VARS:
        if name not in os.environ:
            continue
        active_amd_controls.append(name)
        matched = _filter_by_tokens(
            amd,
            _parse_visible_devices(os.environ[name]),
            allow_uuid=name == "ROCR_VISIBLE_DEVICES",
        )
        if len(active_amd_controls) == 1:
            selected_amd = matched
        else:
            selected_amd = [
                device
                for device in selected_amd
                if any(device is candidate for candidate in matched)
            ]

    warnings = []
    if len(active_amd_controls) > 1:
        warnings.append(
            "AMD visibility controls were intersected; runtime and cgroup "
            "visibility may differ"
        )

    selected = [*selected_nvidia, *selected_amd, *other]
    return _context(selected, env, mode="visible_only", warnings=warnings)
