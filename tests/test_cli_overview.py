"""CLI overview behavior tests."""

from __future__ import annotations

import json
import os
import time

from omnismi.backends.base import BaseBackend
from omnismi.cli import _VISIBILITY_CONTROL_ENV_VARS, _detect_environment, main
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


class _PartialBackend(BaseBackend):
    vendor = "nvidia"

    def available(self) -> bool:
        return True

    def devices(self) -> list[object]:
        return ["h0"]

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
            utilization_percent=55.0,
            memory_used_bytes=8 * 1024**3,
            memory_total_bytes=80 * 1024**3,
            temperature_c=None,
            power_w=None,
            core_clock_mhz=1700.0,
            memory_clock_mhz=1593.0,
            timestamp_ns=time.time_ns(),
        )


def _set_fixed_environment(
    monkeypatch,
    *,
    torch_count: int | None = 2,
    execution_scope: str = "container",
    orchestrator: str = "kubernetes",
    visibility_scope: str = "runtime-scoped",
    visibility_controls: list[dict[str, str]] | None = None,
) -> None:
    monkeypatch.setattr(
        "omnismi.cli._detect_environment",
        lambda: {
            "platform": "linux",
            "hostname": "worker-a17",
            "execution_scope": execution_scope,
            "orchestrator": orchestrator,
            "visibility_scope": visibility_scope,
            "visibility_controls": list(visibility_controls or []),
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


def test_detect_environment_reports_host_global_scope(monkeypatch) -> None:
    for name in ("KUBERNETES_SERVICE_HOST", *_VISIBILITY_CONTROL_ENV_VARS):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("omnismi.cli._looks_like_container", lambda: False)
    monkeypatch.setattr("omnismi.cli._torch_visible_device_count", lambda: 4)
    monkeypatch.setattr("omnismi.cli.platform.system", lambda: "Linux")
    monkeypatch.setattr("omnismi.cli.socket.gethostname", lambda: "host-a17")

    environment = _detect_environment()

    assert environment == {
        "platform": "linux",
        "hostname": "host-a17",
        "execution_scope": "host",
        "orchestrator": "none",
        "visibility_scope": "host-global",
        "visibility_controls": [],
        "torch_visible_device_count": 4,
    }


def test_detect_environment_reports_runtime_scoped_kubernetes_filters(monkeypatch) -> None:
    for name in _VISIBILITY_CONTROL_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "10.0.0.1")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "0,2")
    monkeypatch.setenv("NVIDIA_VISIBLE_DEVICES", "GPU-1234,GPU-5678")
    monkeypatch.setattr("omnismi.cli._looks_like_container", lambda: True)
    monkeypatch.setattr("omnismi.cli._torch_visible_device_count", lambda: 2)
    monkeypatch.setattr("omnismi.cli.platform.system", lambda: "Linux")
    monkeypatch.setattr("omnismi.cli.socket.gethostname", lambda: "trainer-pod")

    environment = _detect_environment()

    assert environment["execution_scope"] == "container"
    assert environment["orchestrator"] == "kubernetes"
    assert environment["visibility_scope"] == "runtime-scoped"
    assert environment["torch_visible_device_count"] == 2
    assert environment["visibility_controls"] == [
        {"name": "CUDA_VISIBLE_DEVICES", "value": "0,2"},
        {"name": "NVIDIA_VISIBLE_DEVICES", "value": "GPU-1234,GPU-5678"},
    ]


def test_main_default_overview_table_output(backend_factories, monkeypatch, capsys) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(monkeypatch)

    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Omnismi v1.0.0 [Host: worker-a17] [IP: 192.168.1.50] [Uptime: 12d 4h 0m] [Status: OK]" in captured.out
    assert "[SYSTEM] CPU: 12% | Mem: 128.0GB/512.0GB | Driver: 550.54.15" in captured.out
    assert "[VISIBLE] Devices: 2 | Vendors: nvidia(2) | Scope: container | Torch: 2" in captured.out
    assert "NVIDIA H100 PCIe" in captured.out
    assert "[||||" in captured.out
    assert "Tips:" in captured.out


def test_main_wide_output_adds_runtime_block(backend_factories, monkeypatch, capsys) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(monkeypatch)

    exit_code = main(["--wide"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[VISIBLE] Devices: 2 | Vendors: nvidia(2) | Scope: container | Backends: nvidia:ok" in captured.out
    assert "DRIVER" in captured.out
    assert "Runtime:" in captured.out
    assert "- execution_scope=container" in captured.out
    assert "- orchestrator=kubernetes" in captured.out
    assert "- visibility_scope=runtime-scoped" in captured.out
    assert "- visibility_controls=none" in captured.out
    assert "backend_status=nvidia:ok" in captured.out


def test_main_default_output_surfaces_active_visibility_filters(
    backend_factories, monkeypatch, capsys
) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(
        monkeypatch,
        visibility_controls=[{"name": "CUDA_VISIBLE_DEVICES", "value": "0,1"}],
    )

    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Filters: CUDA_VISIBLE_DEVICES" in captured.out


def test_main_color_always_emits_ansi_sequences(backend_factories, monkeypatch, capsys) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(monkeypatch)

    exit_code = main(["--color", "always"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "\x1b[" in captured.out


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
    assert payload["environment"]["visibility_scope"] == "runtime-scoped"
    assert payload["environment"]["visibility_controls"] == []
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
    assert "[Status: EMPTY]" in captured.out
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


def test_doctor_reports_visibility_mismatch(backend_factories, monkeypatch, capsys) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(monkeypatch, torch_count=1)

    exit_code = main(["doctor"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Omnismi Doctor v1.0.0 [Host: worker-a17] [Scope: container] [Status: WARN]" in captured.out
    assert "[FINDINGS]" in captured.out
    assert "[RUNTIME]" in captured.out
    assert "PyTorch reports 1 visible GPU(s), but Omnismi found 2." in captured.out
    assert "Compare `torch.cuda.device_count()` with `omnismi -o json`." in captured.out


def test_doctor_mentions_visibility_controls_when_devices_are_missing(
    backend_factories, monkeypatch, capsys
) -> None:
    backend_factories([])
    _set_fixed_environment(
        monkeypatch,
        torch_count=1,
        visibility_controls=[{"name": "CUDA_VISIBLE_DEVICES", "value": "0"}],
    )

    exit_code = main(["doctor"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Runtime visibility controls may intentionally limit which devices the current process can see." in captured.out
    assert "Review active visibility controls such as `CUDA_VISIBLE_DEVICES`" in captured.out
    assert "visibility_controls=CUDA_VISIBLE_DEVICES=0" in captured.out


def test_doctor_reports_partial_device_metrics(backend_factories, monkeypatch, capsys) -> None:
    backend_factories([_PartialBackend])
    _set_fixed_environment(monkeypatch, torch_count=1)

    exit_code = main(["doctor"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Device 0 has partial metrics or missing fields." in captured.out
    assert "Metrics can be partially unavailable" in captured.out


def test_doctor_json_output_uses_doctor_report_schema(
    backend_factories, monkeypatch, capsys
) -> None:
    backend_factories([_DummyBackend])
    _set_fixed_environment(monkeypatch, torch_count=2)

    exit_code = main(["doctor", "-o", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["kind"] == "DoctorReport"
    assert payload["summary"]["status"] == "OK"
    assert payload["summary"]["finding_count"] == 0
