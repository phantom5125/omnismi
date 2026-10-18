"""Document-shaped synthetic telemetry; not readings from real hardware."""

from __future__ import annotations

import pytest

from omnismi.backends import alibaba_ppu as ppu
from omnismi.backends.ppu_telemetry import parse_ppu_query
from omnismi.errors import BackendError

QUERY = """PPU 00000000:01:00.0
    PPU UUID : PPU-test
    Utilization
        Ppu : 38 %
    Temperature
        PPU Current Temp : 42 C
    Power Readings
        Power Draw : 51.99 W
    Clocks
        CU : 200 MHz
        Memory : 1800 MHz
    ECC Errors
        Volatile
            DRAM Uncorrectable : 0
"""


def test_ppu_units_sections_and_uuid_join(monkeypatch):
    raw = ",".join(ppu.FIELDS) + "\n0, PPU, PPU-test, 0000:01:00.0, driver, 1024, 16\n"
    monkeypatch.setattr(ppu.shutil, "which", lambda _: "/ppu-smi")
    monkeypatch.setattr(
        ppu, "query_text", lambda args: QUERY if args[-1] == "-q" else raw
    )
    backend = ppu.AlibabaPpuBackend()
    metric = backend.metrics(backend.devices()[0], 0)
    assert metric.utilization_percent == 38
    assert metric.temperature_c == 42
    assert metric.power_w == 51.99
    assert metric.core_clock_mhz == 200 and metric.memory_clock_mhz == 1800
    backend._telemetry_until = 0
    monkeypatch.setattr(
        ppu, "query_text", lambda args: QUERY.replace("PPU-test", "PPU-replaced")
    )
    assert backend.metrics("PPU-test", 0).power_w is None
    assert "UUID" in backend._telemetry_error


@pytest.mark.parametrize(
    "text",
    [
        QUERY.replace("51.99 W", "51.99 mW"),
        QUERY.replace("38 %", "101 %"),
        QUERY + QUERY,
        "unknown output",
    ],
)
def test_unknown_units_and_ambiguous_snapshots_fail(text):
    with pytest.raises((BackendError, ValueError)):
        parse_ppu_query(text)


def test_missing_values_are_not_zero():
    result = parse_ppu_query(QUERY.replace("51.99 W", "N/A"))["0000:01:00.0"]
    assert result["metrics"]["power_w"] is None
    assert result["ecc"]["Volatile/DRAM Uncorrectable"] == 0
