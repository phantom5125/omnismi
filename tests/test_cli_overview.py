"""CLI overview behavior tests."""

from __future__ import annotations

import json
import time

from omnismi.backends.base import BaseBackend
from omnismi.cli import main
from omnismi.models import GPUMetrics, GPUInfo


class _DummyBackend(BaseBackend):
    vendor = "nvidia"

    def available(self) -> bool:
        return True

    def devices(self) -> list[object]:
        return ["h0", "h1"]

    def info(self, device: object, index: int) -> GPUInfo:
        return GPUInfo(
            index=index,
            vendor="nvidia",
            name="NVIDIA H100 PCIe",
            uuid=f"GPU-{index}",
            driver="550.54.15",
            memory_total_bytes=80 * 1024**3,
        )

    def metrics(self, device: object, index: int) -> GPUMetrics:
        return GPUMetrics(
            index=index,
            utilization_percent=70.0 - index,
            memory_used_bytes=(12 + index) * 1024**3,
            memory_total_bytes=80 * 1024**3,
            temperature_c=58.0 - index,
            power_w=246.0 - index,
            core_clock_mhz=1830.0 - index,
            memory_clock_mhz=1593.0,
            timestamp_ns=time.time_ns(),
        )


def _set_fixed_environment(monkeypatch, *, torch_count: int | None = 2) -> None:
    monkeypatch.setattr(
        "omnismi.cli._detect_environment",
        lambda: {
            "platform": "linux",
            "hostname": "worker-a17",
            "execution_scope": "container",
            "orchestrator": "kubernetes",
            "torch_visible_device_count": torch_count,
        },
    )


def test_main_default_overview_table_output(backend_factories, monkeypatch, capsys) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(monkeypatch)

    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Omnismi 1.0.0  host=worker-a17  env=container  status=OK" in captured.out
    assert "Visible accelerators: 2  vendors=nvidia  scope=runtime-visible" in captured.out
    assert "NVIDIA H100 PCIe" in captured.out
    assert "Tips:" in captured.out


def test_main_wide_output_adds_runtime_block(backend_factories, monkeypatch, capsys) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(monkeypatch)

    exit_code = main(["--wide"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "orchestrator=kubernetes" in captured.out
    assert "Runtime:" in captured.out
    assert "- execution_scope=container" in captured.out
    assert "backend_status=nvidia:ok" in captured.out


def test_main_json_output_matches_overview_schema(backend_factories, monkeypatch, capsys) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(monkeypatch)

    exit_code = main(["-o", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["apiVersion"] == "omnismi/v1alpha1"
    assert payload["kind"] == "OverviewReport"
    assert payload["command"]["argv"] == ["omnismi", "-o", "json"]
    assert payload["summary"]["device_count"] == 2
    assert payload["summary"]["overall_status"] == "OK"
    assert payload["inventory"]["devices"][0]["state"] == "OK"


def test_main_yaml_output_matches_overview_schema(backend_factories, monkeypatch, capsys) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(monkeypatch)

    exit_code = main(["-o", "yaml"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "apiVersion: omnismi/v1alpha1" in captured.out
    assert "kind: OverviewReport" in captured.out
    assert "visibility_status: MATCHED" in captured.out


def test_main_handles_no_visible_devices(backend_factories, monkeypatch, capsys) -> None:
    backend_factories([])
    _set_fixed_environment(monkeypatch, torch_count=None)

    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "status=EMPTY" in captured.out
    assert "No supported accelerators are visible in the current runtime." in captured.out


def test_main_reports_missing_requested_device_indexes(
    backend_factories, monkeypatch, capsys
) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(monkeypatch)

    exit_code = main(["--device", "3", "-o", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["summary"]["device_count"] == 0
    assert payload["summary"]["warnings"] == [
        "Requested device indexes were not visible in the current runtime: 3"
    ]
