"""Passive evidence aggregation without a physical device or SDK."""

from __future__ import annotations

import json

from omnismi.diagnostics import hardware
from omnismi.diagnostics.ras import collect_ras
from omnismi.models import GPUInfo, GPUMetrics


def test_ras_preserves_block_pci_and_evidence_uniqueness(tmp_path):
    for address in ("0000:41:00.0", "0000:42:00.0"):
        device = tmp_path / "bus/pci/devices" / address
        (device / "ras").mkdir(parents=True)
        (device / "vendor").write_text("0x1002\n")
        (device / "ras/umc_err_count").write_text("ce: 3\nue: 0\n")
    result = collect_ras(tmp_path)
    assert result["status"] == "ok" and len(result["reports"]) == 2
    evidence = [e["id"] for report in result["reports"] for e in report["evidence"]]
    assert len(evidence) == len(set(evidence)) == 4
    assert result["reports"][0]["status"] == "WARN"
    assert (
        result["reports"][0]["evidence"][0]["count_semantics"] == "snapshot_not_delta"
    )


def test_hardware_snapshot_reports_historical_ppu_ecc(monkeypatch):
    class Ppu:
        vendor = "alibaba"
        _telemetry_error = None
        _records = {"PPU-test": {"uuid": "PPU-test", "pci_address": "0000:41:00.0"}}
        _telemetry = {
            "0000:41:00.0": {
                "uuid": "PPU-test",
                "ecc": {"Volatile/DRAM Uncorrectable": 2},
            }
        }

        def available(self):
            return True

        def devices(self):
            return ["PPU-test"]

        def info(self, device, index):
            return GPUInfo(index, "alibaba", "PPU", device, "test", 1024)

        def metrics(self, device, index):
            return GPUMetrics(index, 0, 0, 1024, 42, 10, 100, 100, 1)

        def close(self):
            pass

    monkeypatch.setattr(hardware, "registered_backends", lambda: [Ppu()])
    monkeypatch.setattr(
        hardware,
        "collect_kernel_log",
        lambda **kw: {"status": "permission_denied", "text": "", "reason": "denied"},
    )
    report = hardware.collect_snapshot("alibaba")
    assert report["status"] == "FAIL"
    finding = report["data"]["findings"][0]
    assert finding["count"] == 2
    assert finding["count_semantics"] == "volatile_snapshot_not_delta"
    assert finding["hardware_assessment"] == "unconfirmed"
    assert report["data"]["devices"][0]["metrics"]["temperature_c"] == 42
    assert report["scope"]["current_hardware_health"] == "INCONCLUSIVE"
    json.dumps(report, allow_nan=False)


def test_hardware_timeout_retains_inconclusive(monkeypatch):
    from omnismi.errors import BackendError

    def timeout(*args, **kwargs):
        raise BackendError("deadline exceeded")

    monkeypatch.setattr(hardware, "query_text", timeout)
    report = hardware.collect_hardware(timeout=1)
    assert report["status"] == "INCONCLUSIVE"
    assert report["data"]["collection"]["status"] == "incomplete"
