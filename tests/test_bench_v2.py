"""Suite deadlines, early termination and formerly reserved CLI commands."""

import json

import pytest

from omnismi import probe_runtime
from omnismi.cli import main


def test_suite_shares_one_deadline_and_retains_each_report(monkeypatch):
    clock = [0]
    calls = []
    monkeypatch.setattr(probe_runtime.time, "monotonic", lambda: clock[0])

    def execute(**kwargs):
        calls.append(kwargs)
        clock[0] += 2
        return {"status": "PASS", "data": {"captured": kwargs["mode"]}}

    monkeypatch.setattr(probe_runtime, "run_probe", execute)
    report = probe_runtime.run_suite(vendor="nvidia", timeout=10)
    assert report["status"] == "PASS"
    assert [call["timeout"] for call in calls] == [10, 8, 6, 4]
    assert [(call["mode"], call["pattern"]) for call in calls] == [
        ("self-test", "copy"),
        ("bandwidth", "copy"),
        ("bandwidth", "triad"),
        ("compute", "copy"),
    ]
    assert report["scope"]["current_hardware_health"] == "INCONCLUSIVE"
    assert report["scope"]["performance_expectation"] == "not_evaluated"


@pytest.mark.parametrize("status", ["FAIL", "INCONCLUSIVE"])
def test_suite_stops_after_failure_or_missing_runtime(monkeypatch, status):
    calls = []

    def execute(**kwargs):
        calls.append(kwargs)
        return {"status": status, "data": {"reason": "test"}}

    monkeypatch.setattr(probe_runtime, "run_probe", execute)
    report = probe_runtime.run_suite(vendor="alibaba")
    assert report["status"] == status
    assert len(calls) == 1
    assert len(report["data"]["skipped"]) == 3


def test_suite_validates_before_launch_and_reports_exhausted_deadline(monkeypatch):
    monkeypatch.setattr(
        probe_runtime, "run_probe", lambda **kw: pytest.fail("No launch")
    )
    with pytest.raises(ValueError):
        probe_runtime.run_suite(vendor="nvidia", memory_mib=0)
    clock = iter([0, 2, 2, 2, 2])
    monkeypatch.setattr(probe_runtime.time, "monotonic", lambda: next(clock))
    report = probe_runtime.run_suite(vendor="nvidia", timeout=1)
    assert report["status"] == "INCONCLUSIVE"
    assert not report["data"]["results"]
    assert {entry["reason"] for entry in report["data"]["skipped"]} == {
        "suite_deadline_exhausted"
    }


def test_matmul_and_suite_commands_dispatch_explicit_workloads(monkeypatch, capsys):
    from omnismi import bench_v2

    calls = []

    def execute(**kwargs):
        calls.append(kwargs)
        return {"status": "PASS"}

    monkeypatch.setattr(bench_v2, "run_probe", execute)
    monkeypatch.setattr(bench_v2, "run_suite", execute)
    assert main(["bench", "matmul", "--vendor", "alibaba", "--device", "2"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"
    assert calls[0]["mode"] == "compute" and calls[0]["device"] == 2
    assert main(["bench", "suite", "--vendor", "cambricon", "--timeout", "45"]) == 0
    assert calls[1]["timeout"] == 45
    assert "mode" not in calls[1]
    assert main(["bench", "suite"]) == 64
    assert len(calls) == 2
