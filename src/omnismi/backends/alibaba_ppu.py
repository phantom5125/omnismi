"""Experimental SAIL PPU-SMI adapter using the documented CSV query interface."""

from __future__ import annotations

import csv
import io
import re
import shutil
import threading
import time
from decimal import Decimal, DecimalException
from typing import Any

from omnismi.backends.base import BaseBackend
from omnismi.backends.command import query_text
from omnismi.backends.ppu_telemetry import parse_ppu_query
from omnismi.errors import BackendError
from omnismi.identity import normalize_bdf
from omnismi.models import GPUInfo, GPUMetrics

FIELDS = (
    "index",
    "name",
    "uuid",
    "pci.bus_id",
    "driver_version",
    "memory.total",
    "memory.used",
)
_MISSING = {"", "n/a", "[not supported]", "not supported"}


def _text(value: str) -> str | None:
    value = value.strip()
    return None if value.lower() in _MISSING else value


def _memory(value: str) -> int | None:
    if _text(value) is None:
        return None
    try:
        amount = Decimal(value) * 1024**2
        if (
            not amount.is_finite()
            or not 0 <= amount < 2**63
            or amount != amount.to_integral_value()
        ):
            raise ValueError
        return int(amount)
    except (DecimalException, ValueError) as exc:
        raise BackendError("Invalid PPU-SMI memory value (expected MiB)") from exc


def parse_ppu_csv(text: str) -> dict[str, dict[str, Any]]:
    """Parse exactly the requested columns; unknown output is an error."""
    reader = csv.reader(io.StringIO(text), skipinitialspace=True, strict=True)
    try:
        rows = list(reader)
    except csv.Error as exc:
        raise BackendError("Malformed PPU-SMI CSV") from exc
    if not rows or tuple(x.strip() for x in rows[0]) != FIELDS:
        raise BackendError("Unrecognized PPU-SMI CSV header")
    result = {}
    indexes = set()
    addresses = set()
    for row in rows[1:]:
        if not row:
            continue
        if len(row) != len(FIELDS):
            raise BackendError("Incomplete PPU-SMI CSV row")
        record = dict(zip(FIELDS, (x.strip() for x in row)))
        if not record["index"].isdecimal() or not _text(record["name"]):
            raise BackendError("Invalid PPU device identity")
        address = record["pci.bus_id"].lower()
        if not re.fullmatch(r"[0-9a-f]{4,8}:[0-9a-f]{2}:[0-1][0-9a-f]\.[0-7]", address):
            raise BackendError("PPU PCI identity is missing or malformed")
        address = normalize_bdf(address)
        key = _text(record["uuid"]) or address
        if key in result or int(record["index"]) in indexes or address in addresses:
            raise BackendError("Duplicate PPU device identity")
        indexes.add(int(record["index"]))
        addresses.add(address)
        total, used = _memory(record["memory.total"]), _memory(record["memory.used"])
        if total is not None and used is not None and used > total:
            raise BackendError("PPU used memory exceeds total memory")
        result[key] = {
            "name": record["name"],
            "uuid": _text(record["uuid"]),
            "pci_address": address,
            "driver": _text(record["driver_version"]),
            "memory_total_bytes": total,
            "memory_used_bytes": used,
        }
    return result


class AlibabaPpuBackend(BaseBackend):
    """Physical PPU snapshots with optional documented telemetry sections."""

    vendor = "alibaba"

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._sample_time_ns = 0
        self._next_refresh = 0.0
        self._import_failed = False
        self._lock = threading.Lock()
        self._telemetry: dict[str, dict[str, Any]] = {}
        self._telemetry_until = 0.0
        self._telemetry_error: str | None = None

    def _snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            if time.monotonic() >= self._next_refresh:
                executable = shutil.which("ppu-smi")
                self._import_failed = executable is None
                self._records = {}
                if executable is not None:
                    raw = query_text(
                        [
                            executable,
                            "--query-ppu=" + ",".join(FIELDS),
                            "--format=csv,nounits",
                        ]
                    )
                    self._records = parse_ppu_csv(raw)
                self._sample_time_ns = time.time_ns()
                for record in self._records.values():
                    record["timestamp_ns"] = self._sample_time_ns
                self._next_refresh = time.monotonic() + 0.5
            return self._records

    def available(self) -> bool:
        return bool(self._snapshot())

    def devices(self) -> list[Any]:
        return list(self._snapshot())

    def _record(self, device: Any) -> dict[str, Any]:
        record = self._snapshot().get(device)
        if record is None:
            raise BackendError("PPU is no longer visible in the management snapshot")
        return record

    def info(self, device: Any, index: int) -> GPUInfo:
        data = self._record(device)
        return GPUInfo(
            index=index,
            vendor=self.vendor,
            name=data["name"],
            uuid=data["uuid"],
            driver=data["driver"],
            memory_total_bytes=data["memory_total_bytes"],
        )

    def metrics(self, device: Any, index: int) -> GPUMetrics:
        data = self._record(device)
        with self._lock:
            if time.monotonic() >= self._telemetry_until:
                self._telemetry = {}
                try:
                    executable = shutil.which("ppu-smi")
                    if executable is None:
                        raise BackendError("PPU-SMI is unavailable")
                    self._telemetry = parse_ppu_query(query_text([executable, "-q"]))
                    self._telemetry_error = None
                except (OSError, ValueError, BackendError) as exc:
                    self._telemetry_error = str(exc)
                self._telemetry_until = time.monotonic() + 0.5
            telemetry = self._telemetry.get(data["pci_address"], {})
            if telemetry and (
                not data["uuid"] or telemetry.get("uuid") != data["uuid"]
            ):
                self._telemetry_error = "PPU UUID missing or changed between snapshots"
                telemetry = {}
            values = telemetry.get("metrics", {})
        return GPUMetrics(
            index=index,
            utilization_percent=values.get("utilization_percent"),
            memory_used_bytes=data["memory_used_bytes"],
            memory_total_bytes=data["memory_total_bytes"],
            temperature_c=values.get("temperature_c"),
            power_w=values.get("power_w"),
            core_clock_mhz=values.get("core_clock_mhz"),
            memory_clock_mhz=values.get("memory_clock_mhz"),
            timestamp_ns=data["timestamp_ns"],
        )

    def close(self) -> None:
        with self._lock:
            self._records = {}
            self._next_refresh = 0.0
            self._telemetry = {}
            self._telemetry_until = 0.0
