"""Baseline provenance and explicit workload boundaries, without hardware."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from omnismi.baselines import build_baseline
from omnismi.cli import main
from omnismi.diagnostics import decode_error, diagnose
from omnismi.probe_runtime import run_probe


def measurements():
    source = (
        Path(__file__).parents[1] / "examples/performance/synthetic-measurement.json"
    )
    first = json.loads(source.read_text())
    first["value"] = 80
    first["source"]["id"] = "sample-a"
    second = copy.deepcopy(first)
    second["value"] = 100
    second["source"]["id"] = "sample-b"
    return [first, second]


def test_baseline_retains_runs_and_computes_independent_statistics():
    items = measurements()
    baseline = build_baseline(items, baseline_id="lab-1")
    reference = baseline["references"]["expected_sustained"]
    assert reference["value"] == 90
    assert reference["standard_deviation"] == pytest.approx(200**0.5)
    assert reference["sample_count"] == 2
    assert reference["run_ids"] == ["sample-a", "sample-b"]
    items[0]["value"] = 999
    assert baseline["measurements"][0]["value"] == 80
    assert "policy" not in baseline


@pytest.mark.parametrize(
    "case", ["duplicate", "condition", "unknown", "nonfinite", "one"]
)
def test_baseline_rejects_ineligible_runs(case):
    items = measurements()
    if case == "duplicate":
        items[1]["source"]["id"] = "sample-a"
    elif case == "condition":
        items[1]["signature"]["driver_version"] = "changed"
    elif case == "unknown":
        items[0]["signature"]["partition"] = "unknown"
    elif case == "nonfinite":
        items[1]["value"] = float("nan")
    else:
        items.pop()
    with pytest.raises(ValueError):
        build_baseline(items, baseline_id="invalid")


def test_baseline_cli_and_explicit_run_save(monkeypatch, tmp_path, capsys):
    items = measurements()
    paths = [tmp_path / f"{i}.json" for i in range(2)]
    for path, item in zip(paths, items):
        path.write_text(json.dumps(item))
    assert (
        main(
            [
                "perf-doctor",
                "--build-baseline",
                "test",
                "--measurement",
                str(paths[0]),
                "--measurement",
                str(paths[1]),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["baseline_id"] == "test"
    from omnismi import perf_cli

    calls = []

    def probe(**kwargs):
        calls.append(kwargs)
        return {
            "status": "PASS",
            "scope": {},
            "data": {"measurement": items[0], "samples": []},
        }

    monkeypatch.setattr(perf_cli, "run_probe", probe)
    target = tmp_path / "live.json"
    assert (
        main(
            [
                "perf-doctor",
                "--run",
                "bandwidth",
                "--vendor",
                "nvidia",
                "--save-measurement",
                str(target),
            ]
        )
        == 3
    )
    assert json.loads(target.read_text())["value"] == 80
    assert len(calls) == 1
    assert (
        main(
            [
                "perf-doctor",
                "--run",
                "bandwidth",
                "--vendor",
                "nvidia",
                "--save-measurement",
                str(target),
            ]
        )
        == 64
    )
    assert len(calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"memory_mib": 0},
        {"device": -1},
        {"repeats": 1},
        {"timeout": float("nan")},
        {"timeout": 601},
    ],
)
def test_probe_resource_validation_precedes_launch(monkeypatch, change):
    import omnismi.probe_runtime as runtime

    monkeypatch.setattr(
        runtime, "query_text", lambda *a, **kw: pytest.fail("Must not launch")
    )
    with pytest.raises(ValueError):
        run_probe(mode="self-test", vendor="nvidia", **change)


def test_probe_failure_is_inconclusive_and_self_test_is_explicit(monkeypatch, capsys):
    import omnismi.probe_runtime as runtime
    from omnismi.errors import BackendError

    def unavailable(*args, **kwargs):
        raise BackendError("timed out")

    monkeypatch.setattr(runtime, "query_text", unavailable)
    report = run_probe(mode="self-test", vendor="nvidia", timeout=1)
    assert report["status"] == "INCONCLUSIVE"
    assert main(["diagnose", "--self-test"]) == 64
    assert main(["diagnose", "--self-test", "--vendor", "nvidia"]) == 3
    assert json.loads(capsys.readouterr().out)["scope"]["explicit_execution"]


def test_ppu_generations_and_normalized_events_do_not_cross_decode():
    old = decode_error("alibaba", "xid-ppu001", 2706)
    new = decode_error("alibaba", "xid-ppu0015", 2706)
    assert old["data"]["findings"][0]["recognized"]
    assert not new["data"]["findings"][0]["recognized"]
    report = diagnose(
        json.dumps(
            [
                {
                    "vendor": "alibaba",
                    "namespace": "xid-ppu0015",
                    "code": 4997,
                    "pci_address": "0000:41:00.0",
                }
            ]
        ),
        input_format="events",
    )
    assert report["status"] == "FAIL"
    assert "alibaba:HBM" in report["data"]["findings"][0]["affected_units"]
    assert report["scope"]["current_hardware_health"] == "INCONCLUSIVE"


@pytest.mark.parametrize(
    "event",
    [
        {"vendor": "alibaba", "namespace": "xid", "code": True},
        {"vendor": "nvidia", "namespace": "xid", "code": 48, "pci_address": "bad"},
        {"vendor": "amd", "namespace": "ras", "code": "ue"},
    ],
)
def test_invalid_normalized_event_rejected(event):
    with pytest.raises(ValueError):
        diagnose(json.dumps([event]), input_format="events")


def test_current_nvidia_catalog_model_gates_and_non_error_events():
    report = decode_error("nvidia", "xid", 119)
    assert report["data"]["findings"][0]["title"] == "GSP_RPC_TIMEOUT"
    assert report["data"]["findings"][0]["vendor_recovery_bucket"] == "RESET_GPU"
    assert report["data"]["findings"][0]["actions_executed"] is False
    report = decode_error("nvidia", "xid", 106)
    assert report["status"] == "INCONCLUSIVE"
    from omnismi.diagnostics.catalog import load_catalog

    rule = next(
        r
        for r in load_catalog()["rules"]
        if r.get("catalog_model_applicability", {}).get("A100") is False
    )
    report = decode_error(
        "nvidia", "xid", rule["code"], context={"model": "NVIDIA A100"}
    )
    assert report["data"]["findings"][0]["assessment"] == "catalog_model_mismatch"


def test_driver_uuid_normalization_and_pci_prefix():
    report = diagnose(
        "[ 1] NVRM: GPU at 0000:03:00: GPU-1234-abcd\n"
        "[ 2] NVRM: Xid (PCI:0000:03:00): 48, error"
    )
    finding = next(f for f in report["data"]["findings"] if f["code"] == "48")
    assert finding["uuid"] == "GPU-1234-abcd"
    assert finding["pci_address"] == "0000:03:00"
