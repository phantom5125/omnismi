"""CLI bench behavior tests."""

from __future__ import annotations

import json
import os
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
            "visibility_scope": "runtime-scoped",
            "visibility_controls": [],
            "torch_visible_device_count": torch_count,
        },
    )
    monkeypatch.setattr(
        "omnismi.cli._collect_system_metrics",
        lambda devices, backends: {
            "ip_address": "192.168.1.50",
            "uptime_seconds": 12 * 86400 + 4 * 3600,
            "cpu_percent": 12.0,
            "memory_used_bytes": 128 * 1024**3,
            "memory_total_bytes": 512 * 1024**3,
            "net_rx_bytes_per_s": None,
            "net_tx_bytes_per_s": None,
            "driver_label": "550.54.15",
        },
    )
    monkeypatch.setattr(
        "omnismi.cli.shutil.get_terminal_size",
        lambda fallback=(100, 20): os.terminal_size((120, 40)),
    )


def _mock_bench_result(
    *,
    execution_status: str = "success",
    bandwidth_bytes_per_second: float = 512 * 1024**3,
    include_samples: bool = False,
) -> dict[str, object]:
    errors = [] if execution_status == "success" else ["runtime unavailable"]
    metrics = {
        "buffer_bytes": 256 * 1024**2,
        "bytes_per_iteration": 512 * 1024**2,
    }
    if execution_status == "success":
        metrics["bandwidth_bytes_per_second"] = bandwidth_bytes_per_second
        metrics["peak_bandwidth_bytes_per_second"] = bandwidth_bytes_per_second * 1.05
    if include_samples and execution_status == "success":
        metrics["sample_bandwidth_bytes_per_second"] = [
            bandwidth_bytes_per_second * 0.98,
            bandwidth_bytes_per_second,
            bandwidth_bytes_per_second * 1.02,
        ]
    return {
        "execution": {
            "status": execution_status,
            "started_at": "2026-04-23T03:11:02Z",
            "ended_at": "2026-04-23T03:11:05Z",
            "errors": errors,
        },
        "parameters": {
            "runtime": "torch",
            "pattern": "copy",
            "dtype": "fp32",
            "buffer_bytes": 256 * 1024**2,
            "minimum_iterations": 20,
            "warmup_seconds": 0.2,
            "duration_seconds": 1.0,
            "repeats": 3,
        },
        "statistics": {
            "sample_count": 3 if execution_status == "success" else 0,
            "min_seconds": 1.0 if execution_status == "success" else None,
            "mean_seconds": 1.1 if execution_status == "success" else None,
            "median_seconds": 1.1 if execution_status == "success" else None,
            "p95_seconds": 1.2 if execution_status == "success" else None,
            "max_seconds": 1.2 if execution_status == "success" else None,
            "stdev_seconds": 0.1 if execution_status == "success" else None,
        },
        "metrics": metrics,
        "samples": metrics.get("sample_bandwidth_bytes_per_second") if include_samples else None,
    }


def test_bench_bandwidth_table_output(backend_factories, monkeypatch, capsys) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(monkeypatch)
    monkeypatch.setattr(
        "omnismi.cli._execute_bandwidth_probe_for_device",
        lambda device, args: _mock_bench_result(),
    )

    exit_code = main(["bench", "bandwidth", "--no-color"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Omnismi Bench v1.0.0 [Host: worker-a17] [Probe: bandwidth] [Status: INCONCLUSIVE]" in captured.out
    assert "copy_fp32_256.0mb" in captured.out
    assert "512.0GB/s" in captured.out
    assert "execution_status=success" in captured.out


def test_bench_bandwidth_json_output_uses_bench_report_schema(
    backend_factories, monkeypatch, capsys
) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(monkeypatch)
    monkeypatch.setattr(
        "omnismi.cli._execute_bandwidth_probe_for_device",
        lambda device, args: _mock_bench_result(include_samples=True),
    )

    exit_code = main(
        ["bench", "bandwidth", "--profile", "h100-pcie-80gb", "--include-samples", "-o", "json"]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["kind"] == "BenchReport"
    assert payload["command"]["subcommand"] == "bandwidth"
    assert payload["profile"]["name"] == "h100-pcie-80gb"
    assert payload["summary"]["verdict_status"] == "INCONCLUSIVE"
    assert payload["results"][0]["metrics"]["sample_bandwidth_bytes_per_second"][0] > 0


def test_bench_bandwidth_no_visible_devices_is_inconclusive(
    backend_factories, monkeypatch, capsys
) -> None:
    backend_factories([])
    _set_fixed_environment(monkeypatch, torch_count=None)

    exit_code = main(["bench", "bandwidth", "--no-color"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[Status: INCONCLUSIVE]" in captured.out
    assert "No visible devices" in captured.out
    assert "No visible devices matched the current benchmark scope." in captured.out


def test_bench_bandwidth_error_result_fails_summary(
    backend_factories, monkeypatch, capsys
) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(monkeypatch)
    monkeypatch.setattr(
        "omnismi.cli._execute_bandwidth_probe_for_device",
        lambda device, args: _mock_bench_result(execution_status="error"),
    )

    exit_code = main(["bench", "bandwidth", "-o", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["summary"]["execution_status"] == "error"
    assert payload["summary"]["verdict_status"] == "FAIL"
    assert payload["results"][0]["execution"]["errors"] == ["runtime unavailable"]


def test_bench_matmul_remains_placeholder(backend_factories, monkeypatch, capsys) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(monkeypatch)

    exit_code = main(["bench", "matmul"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "`omnismi bench matmul` is planned but not implemented yet." in captured.err
