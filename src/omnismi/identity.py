"""Shared vendor-independent device identity normalization."""

from __future__ import annotations

import re


def normalize_bdf(value: str) -> str:
    match = re.fullmatch(
        r"([0-9a-f]{4,8}):([0-9a-f]{2}):([01][0-9a-f])\.([0-7])", value.lower()
    )
    if not match:
        raise ValueError("Invalid PCI identity")
    domain, bus, device, function = match.groups()
    return f"{int(domain, 16):04x}:{bus}:{device}.{function}"
