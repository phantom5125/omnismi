"""Version-scoped SAIL PPU-SMI query sections with explicit units."""

from __future__ import annotations

import math
import re
from typing import Any

from omnismi.errors import BackendError
from omnismi.identity import normalize_bdf

_FIELDS = {
    ("Utilization", "Ppu"): ("utilization_percent", "%", 0, 100),
    ("Temperature", "PPU Current Temp"): ("temperature_c", "C", -100, 300),
    ("Power Readings", "Power Draw"): ("power_w", "W", 0, 100000),
    ("Clocks", "CU"): ("core_clock_mhz", "MHz", 0, 100000),
    ("Clocks", "Memory"): ("memory_clock_mhz", "MHz", 0, 100000),
}


def parse_ppu_query(text: str) -> dict[str, dict[str, Any]]:
    if len(text.encode()) > 1_048_576:
        raise BackendError("PPU query exceeds byte budget")
    result, stack, current = {}, [], None
    for line in text.splitlines():
        header = re.fullmatch(r"PPU ([0-9A-Fa-f:.]+)", line.strip())
        if header:
            address = normalize_bdf(header[1])
            if address in result:
                raise BackendError("Duplicate PPU telemetry identity")
            current = {"uuid": None, "metrics": {}, "ecc": {}}
            result[address] = current
            stack = []
            continue
        if current is None or not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if ":" not in line:
            stack.append((indent, line.strip()))
            continue
        name, value = (part.strip() for part in line.split(":", 1))
        path = tuple(item[1] for item in stack) + (name,)
        if path == ("PPU UUID",):
            if current["uuid"] is not None:
                raise BackendError("Duplicate PPU UUID field")
            current["uuid"] = None if value == "N/A" else value
        elif path in _FIELDS:
            key, unit, minimum, maximum = _FIELDS[path]
            if key in current["metrics"]:
                raise BackendError("Duplicate PPU metric field")
            number = None
            if value != "N/A":
                match = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s+" + re.escape(unit), value)
                if not match:
                    raise BackendError("PPU metric has an unknown unit or format")
                number = float(match[1])
                if not math.isfinite(number) or not minimum <= number <= maximum:
                    raise BackendError("PPU metric is outside its valid range")
            current["metrics"][key] = number
        elif (
            len(path) == 3
            and path[0] == "ECC Errors"
            and path[1] in {"Volatile", "Aggregate"}
        ):
            if path[2] in {
                "SRAM Correctable",
                "SRAM Uncorrectable",
                "DRAM Correctable",
                "DRAM Uncorrectable",
            }:
                if not value.isdecimal() and value != "N/A":
                    raise BackendError("Invalid ECC counter")
                key = "/".join(path[1:])
                if key in current["ecc"]:
                    raise BackendError("Duplicate ECC counter")
                current["ecc"][key] = int(value) if value.isdecimal() else None
    if not result:
        raise BackendError("Unrecognized SAIL PPU-SMI query output")
    return result
