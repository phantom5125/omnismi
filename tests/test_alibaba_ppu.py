"""Synthetic SAIL CSV fixtures; no PPU hardware validation implied."""

from __future__ import annotations

import pytest

from omnismi.backends import alibaba_ppu as ppu
from omnismi.errors import BackendError

HEADER = ", ".join(ppu.FIELDS) + "\n"
ROW = "0, PPU-test, GPU-test, 00000000:01:00.0, 2.1.0-test, 1024, 16\n"


def test_normalized_inventory_memory_and_stable_device_identity(monkeypatch):
    calls = []
    monkeypatch.setattr(ppu.shutil, "which", lambda _: "/test/ppu-smi")
    monkeypatch.setattr(
        ppu, "query_text", lambda args: calls.append(args) or HEADER + ROW
    )
    backend = ppu.AlibabaPpuBackend()
    assert backend.available()
    handle = backend.devices()[0]
    assert handle == "GPU-test"
    assert backend.info(handle, 3).vendor == "alibaba"
    assert backend.info(handle, 3).memory_total_bytes == 1024**3
    metrics = backend.metrics(handle, 3)
    assert metrics.memory_used_bytes == 16 * 1024**2
    assert metrics.utilization_percent is None
    assert metrics.index == 3 and metrics.timestamp_ns > 0
    assert len(calls) == 2
    assert calls[1][1:] == ["-q"]
    assert backend._telemetry_error is not None
    assert calls[0][1].startswith("--query-ppu=")
    assert calls[0][2] == "--format=csv,nounits"
    backend.close()
    assert not backend._records


def test_missing_tool_and_unsupported_values(monkeypatch):
    monkeypatch.setattr(ppu.shutil, "which", lambda _: None)
    backend = ppu.AlibabaPpuBackend()
    assert not backend.available()
    assert backend._import_failed
    result = ppu.parse_ppu_csv(HEADER + ROW.replace("1024, 16", "N/A, N/A"))
    assert result["GPU-test"]["memory_total_bytes"] is None


@pytest.mark.parametrize(
    "body",
    [
        "bad header",
        HEADER + ROW + ROW,
        HEADER + ROW.replace("1024, 16", "1, 2"),
        HEADER + ROW.replace("1024, 16", "NaN, 0"),
        HEADER + ROW.replace("00000000:01:00.0", "unknown"),
        HEADER + ROW.replace("1024, 16", "-1, 0"),
        HEADER + ROW.replace("1024, 16", "1e10000000, 0"),
    ],
)
def test_reject_unknown_or_ambiguous_csv(body):
    with pytest.raises(BackendError):
        ppu.parse_ppu_csv(body)


def test_stale_device_is_not_replaced_by_reused_ordinal(monkeypatch):
    monkeypatch.setattr(ppu.shutil, "which", lambda _: "/test/ppu-smi")
    monkeypatch.setattr(ppu, "query_text", lambda _: HEADER + ROW)
    backend = ppu.AlibabaPpuBackend()
    handle = backend.devices()[0]
    backend.close()
    monkeypatch.setattr(
        ppu, "query_text", lambda _: HEADER + ROW.replace("GPU-test", "GPU-new")
    )
    with pytest.raises(BackendError, match="no longer visible"):
        backend.info(handle, 0)
