"""CNDEV adapter through an SDK-compiled, bounded native process boundary."""

from __future__ import annotations

import json
import math
import os
import shutil
import threading
import time
from decimal import Decimal
from typing import Any

from omnismi.backends.base import BaseBackend
from omnismi.backends.command import query_text
from omnismi.errors import BackendError
from omnismi.models import GPUInfo, GPUMetrics


def parse_snapshot(text: str) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise BackendError("Malformed CNDEV snapshot") from exc
    if (
        not isinstance(payload, dict)
        or type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != 1
        or payload.get("collector") != "omnismi-cndev"
        or payload.get("sdk_api") != 6
    ):
        raise BackendError("Unknown CNDEV collector schema")
    devices = payload.get("devices")
    if not isinstance(devices, list) or len(devices) > 4096:
        raise BackendError("Invalid CNDEV inventory")
    result, indexes = {}, set()
    for item in devices:
        if (
            not isinstance(item, dict)
            or type(item.get("index")) is not int
            or item["index"] < 0
        ):
            raise BackendError("Invalid CNDEV device index")
        uuid, name = item.get("uuid"), item.get("name")
        if (
            not isinstance(uuid, str)
            or not uuid
            or not isinstance(name, str)
            or not name
            or uuid in result
            or item["index"] in indexes
        ):
            raise BackendError("Missing or duplicate CNDEV device identity")
        indexes.add(item["index"])
        record = dict(item)
        for field in (
            "memory_total_mib",
            "memory_used_mib",
            "power_w",
            "core_clock_mhz",
            "memory_clock_mhz",
            "temperature_c",
            "utilization_percent",
        ):
            value = item.get(field)
            minimum = -100 if field == "temperature_c" else 0
            if value is not None and (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or value < minimum
            ):
                raise BackendError(f"Invalid CNDEV metric: {field}")
            if field.endswith("_mib"):
                byte_value = (
                    Decimal(str(value)) * 1024**2 if value is not None else None
                )
                if byte_value is not None and (
                    byte_value >= 2**63 or byte_value != byte_value.to_integral_value()
                ):
                    raise BackendError("Invalid CNDEV memory size")
                record[field.replace("_mib", "_bytes")] = (
                    int(byte_value) if byte_value is not None else None
                )
        if (
            item.get("utilization_percent") is not None
            and item["utilization_percent"] > 100
        ):
            raise BackendError("CNDEV utilization exceeds 100%")
        total, used = record["memory_total_bytes"], record["memory_used_bytes"]
        if total is not None and used is not None and used > total:
            raise BackendError("CNDEV used memory exceeds total")
        result[uuid] = record
    return result


class CambriconBackend(BaseBackend):
    vendor = "cambricon"

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._next_refresh = 0.0
        self._import_failed = False
        self._lock = threading.Lock()

    def _snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            if time.monotonic() >= self._next_refresh:
                executable = os.environ.get("OMNISMI_CNDEV_PROBE") or shutil.which(
                    "omnismi-cndev-probe"
                )
                self._import_failed = executable is None
                self._records = {}
                if executable:
                    self._records = parse_snapshot(
                        query_text([executable, "--snapshot"])
                    )
                timestamp = time.time_ns()
                for record in self._records.values():
                    record["timestamp_ns"] = timestamp
                self._next_refresh = time.monotonic() + 0.5
            return self._records

    def available(self) -> bool:
        return bool(self._snapshot())

    def devices(self) -> list[Any]:
        return list(self._snapshot())

    def _record(self, device: Any) -> dict[str, Any]:
        record = self._snapshot().get(device)
        if record is None:
            raise BackendError("MLU is no longer visible in the CNDEV snapshot")
        return record

    def info(self, device: Any, index: int) -> GPUInfo:
        data = self._record(device)
        return GPUInfo(
            index=index,
            vendor=self.vendor,
            name=data["name"],
            uuid=data["uuid"],
            driver=data.get("driver"),
            memory_total_bytes=data["memory_total_bytes"],
        )

    def metrics(self, device: Any, index: int) -> GPUMetrics:
        data = self._record(device)
        return GPUMetrics(
            index=index,
            timestamp_ns=data["timestamp_ns"],
            **{
                field: data.get(field)
                for field in (
                    "utilization_percent",
                    "memory_used_bytes",
                    "memory_total_bytes",
                    "temperature_c",
                    "power_w",
                    "core_clock_mhz",
                    "memory_clock_mhz",
                )
            },
        )

    def close(self) -> None:
        with self._lock:
            self._records = {}
            self._next_refresh = 0.0
