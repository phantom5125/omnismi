"""Parse accelerator visibility env vars and filter device lists."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class VisibilityContext:
    """How devices were filtered for this snapshot."""

    mode: str
    env: dict[str, str]
    physical_indices: list[int]
    logical_indices: list[int]


def parse_cuda_visible_devices(
    raw: str | None = None,
) -> list[str] | None:
    """Return token list from CUDA_VISIBLE_DEVICES, or None if unset/empty means all.

    Empty string means no devices visible (NVIDIA semantics).
    Unset means all devices.
    """
    if raw is None:
        if "CUDA_VISIBLE_DEVICES" not in os.environ:
            return None
        raw = os.environ["CUDA_VISIBLE_DEVICES"]
    value = raw.strip()
    if value == "":
        return []
    return [part.strip() for part in value.split(",") if part.strip() != ""]


def _uuid_matches(token: str, uuid: str | None) -> bool:
    if not uuid:
        return False
    t = token.lower()
    u = uuid.lower()
    if t == u:
        return True
    # Allow GPU- prefix forms
    if t.startswith("gpu-") and u.startswith("gpu-") and t == u:
        return True
    if not t.startswith("gpu-") and u.endswith(t):
        return True
    return False


def filter_gpus_by_visibility(
    devices: Sequence[object],
    *,
    visible_only: bool = True,
    cuda_visible_devices: str | None = None,
) -> tuple[list[object], VisibilityContext]:
    """Filter GPU-like objects with .index / .info().

    Each device must provide ``index`` and ``info()`` returning an object with
    optional ``uuid``.
    """
    env: dict[str, str] = {}
    if "CUDA_VISIBLE_DEVICES" in os.environ:
        env["CUDA_VISIBLE_DEVICES"] = os.environ["CUDA_VISIBLE_DEVICES"]

    if not visible_only:
        physical = [int(getattr(d, "index")) for d in devices]
        logical = list(range(len(physical)))
        return list(devices), VisibilityContext(
            mode="all",
            env=env,
            physical_indices=physical,
            logical_indices=logical,
        )

    tokens = parse_cuda_visible_devices(cuda_visible_devices)
    if tokens is None:
        physical = [int(getattr(d, "index")) for d in devices]
        logical = list(range(len(physical)))
        return list(devices), VisibilityContext(
            mode="visible_only",
            env=env,
            physical_indices=physical,
            logical_indices=logical,
        )

    if tokens == []:
        return [], VisibilityContext(
            mode="visible_only",
            env=env,
            physical_indices=[],
            logical_indices=[],
        )

    by_index = {int(getattr(d, "index")): d for d in devices}
    selected: list[object] = []
    for token in tokens:
        if token.isdigit() or (token.startswith("-") and token[1:].isdigit()):
            idx = int(token)
            device = by_index.get(idx)
            if device is not None:
                selected.append(device)
            continue
        matched = None
        for device in devices:
            info = device.info()  # type: ignore[attr-defined]
            uuid = getattr(info, "uuid", None)
            if _uuid_matches(token, uuid):
                matched = device
                break
        if matched is not None:
            selected.append(matched)

    physical = [int(getattr(d, "index")) for d in selected]
    logical = list(range(len(physical)))
    return selected, VisibilityContext(
        mode="visible_only",
        env=env,
        physical_indices=physical,
        logical_indices=logical,
    )
