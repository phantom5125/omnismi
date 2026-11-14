"""CLI preflight tests without real accelerators."""

from __future__ import annotations

import json
from contextlib import contextmanager, nullcontext
from dataclasses import replace

import pytest

from omnismi import __version__
from omnismi.cli import main
from omnismi.models import GPUInfo, GPUMetrics
from omnismi.preflight import build_preflight


class FakeBackend:
    vendor = "nvidia"

    def realtime_mode(self):
        return nullcontext()


class FakeGPU:
    def __init__(self, index, free_bytes=8 * 1024**3, vendor="nvidia"):
        self.index = index
        self._backend = FakeBackend()
        self._free = free_bytes
        self._total = 16 * 1024**3
        self._vendor = vendor

    def info(self):
        return GPUInfo(
            index=self.index,
            vendor=self._vendor,
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


def test_build_preflight_unknown_free_memory_does_not_pass():
    class UnknownMemoryGPU(FakeGPU):
        def metrics(self):
            return replace(super().metrics(), memory_used_bytes=None)

    payload = build_preflight(devices=[UnknownMemoryGPU(0)], min_free_bytes=1024**3)

    assert payload["ok"] is False
    assert payload["exit_code"] == 3
    assert payload["failures"] == [
        {
            "code": "free_memory_unknown",
            "device_logical_index": 0,
            "need_free_bytes": 1024**3,
        }
    ]


def test_build_preflight_vendor_scopes_count_and_visibility():
    devices = [FakeGPU(0), FakeGPU(1, vendor="amd")]

    payload = build_preflight(devices=devices, vendor="amd", min_gpus=1)

    assert payload["exit_code"] == 0
    assert payload["requirements"]["vendor"] == "amd"
    assert payload["summary"]["vendors"] == ["amd"]
    assert payload["visibility"]["physical_indices"] == [1]
    assert payload["visibility"]["enforcement"] == "runtime_hint_only"


def test_cli_preflight_json(monkeypatch, capsys):
    monkeypatch.setattr("omnismi.preflight.list_gpus", lambda: [FakeGPU(0)])
    code = main(["preflight"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert code == 0
    assert data["command"] == "preflight"
    assert data["summary"]["gpu_count"] == 1


def test_cli_preflight_vendor_option(monkeypatch, capsys):
    monkeypatch.setattr(
        "omnismi.preflight.list_gpus",
        lambda: [FakeGPU(0), FakeGPU(1, vendor="amd")],
    )

    assert main(["preflight", "--vendor", "amd", "--min-gpus", "1"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["requirements"]["vendor"] == "amd"
    assert [row["physical_index"] for row in data["devices"]] == [1]


@pytest.mark.parametrize(
    "argv",
    [
        ["preflight", "--unknown"],
        ["inventory", "--unknown"],
        ["metrics", "--unknown"],
        ["preflight", "--min-gpus"],
    ],
)
def test_cli_usage_error(argv, capsys):
    assert main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "usage:" in captured.err


@pytest.mark.parametrize(
    "argv", [["preflight", "--help"], ["metrics", "--help"], ["--version"]]
)
def test_cli_help_and_version_succeed(argv, capsys):
    assert main(argv) == 0
    assert capsys.readouterr().out


def test_root_help_preserves_overview_and_lists_agent_commands(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    for option in ("--wide", "--watch", "--vendor", "--version"):
        assert option in output
    for command in ("preflight", "inventory", "metrics", "topology", "diagnose"):
        assert command in output


@pytest.mark.parametrize(
    ("argv", "expected"),
    [(["version"], __version__), (["--version"], f"omnismi {__version__}")],
)
def test_version_reports_current_package_version(argv, expected, capsys):
    assert main(argv) == 0
    assert capsys.readouterr().out.strip() == expected


@pytest.mark.parametrize(
    "arguments",
    [
        ["--min-gpus", "-1"],
        ["--min-free-bytes", "-1"],
        ["--min-free-gib=-0.5"],
        ["--min-free-gib=nan"],
        ["--min-free-gib=inf"],
        ["--min-free-gib=-inf"],
        ["--min-free-gib=1e308"],
    ],
)
def test_cli_rejects_invalid_thresholds(arguments, monkeypatch, capsys):
    def unexpected_discovery():
        pytest.fail("invalid input must be rejected before discovering devices")

    monkeypatch.setattr("omnismi.preflight.list_gpus", unexpected_discovery)
    assert main(["preflight", *arguments]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error:" in captured.err


@pytest.mark.parametrize(
    ("arguments", "expected_bytes"),
    [
        (["--min-gpus", "0", "--min-free-bytes", "0"], 0),
        (["--min-free-gib", "0"], 0),
        (["--min-free-gib", "1.5"], 3 * 1024**3 // 2),
        (["--min-free-bytes", str(2 * 1024**3), "--min-free-gib", "1"], 2 * 1024**3),
    ],
)
def test_cli_valid_thresholds(arguments, expected_bytes, monkeypatch, capsys):
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setattr("omnismi.preflight.list_gpus", lambda: [FakeGPU(0)])
    assert main(["preflight", *arguments]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["requirements"]["min_free_bytes_per_gpu"] == expected_bytes


@pytest.mark.parametrize("command", ["preflight", "inventory", "metrics"])
@pytest.mark.parametrize("empty", [False, True])
def test_cli_snapshot_envelope(command, empty, monkeypatch, capsys):
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setattr(
        "omnismi.preflight.list_gpus", lambda: [] if empty else [FakeGPU(0)]
    )
    expected_code = 2 if empty else 0
    assert main([command]) == expected_code
    data = json.loads(capsys.readouterr().out)
    assert data["command"] == command
    assert data["schema_version"] == 1
    assert data["exit_code"] == expected_code
    assert data["ok"] is (not empty)
    assert isinstance(data["ts_ns"], int) and data["ts_ns"] > 0
    assert data["summary"] == {
        "gpu_count": 0 if empty else 1,
        "vendors": [] if empty else ["nvidia"],
        "all_free_bytes_min": None if empty else 8 * 1024**3,
        "busy_gpu_count": None,
    }
    if empty:
        assert data["failures"][0]["code"] == "no_accelerators"


@pytest.mark.parametrize("command", ["preflight", "inventory", "metrics"])
def test_cli_backend_error_envelope(command, monkeypatch, capsys):
    def fail_discovery():
        raise RuntimeError("discovery unavailable")

    monkeypatch.setattr("omnismi.preflight.list_gpus", fail_discovery)
    assert main([command, "--human"]) == 10
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["command"] == command
    assert data["ok"] is False
    assert isinstance(data["ts_ns"], int) and data["ts_ns"] > 0
    assert data["summary"] == {
        "gpu_count": 0,
        "vendors": [],
        "all_free_bytes_min": None,
        "busy_gpu_count": None,
    }
    assert data["devices"] == []
    assert data["failures"] == [
        {"code": "backend_error", "message": "discovery unavailable"}
    ]
    assert "exit=10" in captured.err


def test_cli_metrics_snapshot_failure(monkeypatch, capsys):
    class BrokenGPU(FakeGPU):
        def metrics(self):
            raise RuntimeError("snapshot unavailable")

    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setattr("omnismi.preflight.list_gpus", lambda: [BrokenGPU(0)])
    assert main(["metrics"]) == 10
    data = json.loads(capsys.readouterr().out)
    assert data["failures"][0]["code"] == "backend_error"


def test_cli_metrics_human_summary(monkeypatch, capsys):
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setattr("omnismi.preflight.list_gpus", lambda: [FakeGPU(0)])
    assert main(["metrics", "--human"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["command"] == "metrics"
    assert "gpus=1 vendors=['nvidia']" in captured.err


@pytest.mark.parametrize(
    ("arguments", "physical_indices"), [([], [1, 0]), (["--all-devices"], [0, 1, 2])]
)
def test_cli_metrics_one_shot_visibility(
    arguments, physical_indices, monkeypatch, capsys
):
    class TrackedGPU(FakeGPU):
        reads = 0
        in_realtime = False

        @contextmanager
        def realtime(self):
            self.in_realtime = True
            try:
                yield
            finally:
                self.in_realtime = False

        def metrics(self):
            assert self.in_realtime
            self.reads += 1
            return super().metrics()

    devices = [TrackedGPU(index) for index in range(3)]
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "1,0")
    monkeypatch.setattr("omnismi.preflight.list_gpus", lambda: devices)
    assert main(["metrics", *arguments]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["visibility"]["physical_indices"] == physical_indices
    assert [row["physical_index"] for row in data["devices"]] == physical_indices
    assert [row["logical_index"] for row in data["devices"]] == list(
        range(len(physical_indices))
    )
    assert [device.reads for device in devices] == [
        int(device.index in physical_indices) for device in devices
    ]
    assert all(not device.in_realtime for device in devices)
