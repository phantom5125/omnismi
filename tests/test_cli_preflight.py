"""CLI preflight tests without real accelerators."""

from __future__ import annotations

import json
from contextlib import nullcontext

from omnismi.cli import main
from omnismi.models import GPUInfo, GPUMetrics
from omnismi.preflight import build_preflight


class FakeBackend:
    vendor = "nvidia"

    def realtime_mode(self):
        return nullcontext()


class FakeGPU:
    def __init__(self, index, free_bytes=8 * 1024**3):
        self.index = index
        self._backend = FakeBackend()
        self._free = free_bytes
        self._total = 16 * 1024**3

    def info(self):
        return GPUInfo(
            index=self.index,
            vendor="nvidia",
            name=f"Fake-{self.index}",
            uuid=f"GPU-fake-{self.index}",
            driver="fake",
            memory_total_bytes=self._total,
        )

    def metrics(self):
        return GPUMetrics(
            index=self.index,
            utilization_percent=0.0,
            memory_used_bytes=self._total - self._free,
            memory_total_bytes=self._total,
            temperature_c=40.0,
            power_w=50.0,
            core_clock_mhz=None,
            memory_clock_mhz=None,
            timestamp_ns=1,
        )

    def realtime(self):
        return nullcontext()


def test_build_preflight_ok():
    payload = build_preflight(devices=[FakeGPU(0), FakeGPU(1)], min_gpus=2)
    assert payload["ok"] is True
    assert payload["exit_code"] == 0
    assert payload["summary"]["gpu_count"] == 2
    assert payload["devices"][0]["processes"] == []
    assert payload["schema_version"] == 1


def test_build_preflight_no_devices():
    payload = build_preflight(devices=[])
    assert payload["exit_code"] == 2
    assert payload["ok"] is False


def test_build_preflight_min_free_fail():
    payload = build_preflight(
        devices=[FakeGPU(0, free_bytes=1)],
        min_free_bytes=1024**3,
    )
    assert payload["exit_code"] == 3
    assert any(f["code"] == "insufficient_free_memory" for f in payload["failures"])


def test_cli_preflight_json(monkeypatch, capsys):
    monkeypatch.setattr(
        "omnismi.preflight.list_gpus", lambda: [FakeGPU(0)]
    )
    code = main(["preflight"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert code == 0
    assert data["command"] == "preflight"
    assert data["summary"]["gpu_count"] == 1


def test_cli_usage_error():
    code = main([])
    assert code == 2  # argparse missing subcommand
