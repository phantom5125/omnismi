"""Campaign orchestration and acceptance gates use software-only report fixtures."""

import copy
import json
import os
import signal
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from omnismi.selftest import acceptance as campaign
from omnismi.selftest.catalog import plan
from omnismi.selftest.cli import run
from omnismi.selftest.targets import target_profile


def passed_report(config):
    report = campaign.canonical(plan(config))
    report.update(
        status="PASS",
        executed=True,
        complete=True,
        phase="finished",
        errors=[],
        failures=[],
        acceptance_gates={
            key: True
            for key in (
                "all_requested_comparisons",
                "load_duration",
                "power_target",
                "physical_unit_coverage",
            )
        },
    )
    report["identity"] = {
        "vendor": config.vendor,
        "name": target_profile(config.target)["name"],
        "uuid": "fixture-device-a" if config.vendor != "google" else None,
        "runtime_device_index": config.device,
        "framework": "jax" if config.vendor == "google" else "pytorch",
        "framework_version": "software-fixture",
        "execution_device": "fixture-only",
    }
    report["results"] = [
        {
            "case": case,
            "status": "PASS",
            "comparisons": 1,
            "executions": 1,
            "phases": (
                ["baseline", "post_load"] if config.profile == "soak" else ["baseline"]
            ),
        }
        for case in report["cases"]
    ]
    if config.profile == "soak":
        report.update(load_seconds=config.duration, load_duration_completed=True)
        report["results"].append(
            {
                "case": {"id": "9000-matmul-load", "operator": "matmul"},
                "status": "PASS",
                "comparisons": 1,
                "executions": 1,
                "phases": ["load"],
            }
        )
    if config.power_target_w is not None:
        report["telemetry"] = {
            "target_w": config.power_target_w,
            "target_observed": True,
            "attribution": "matched_runtime_uuid",
            "samples": [
                {
                    "phase": "load",
                    "timestamp_ns": i + 1,
                    "power_w": config.power_target_w,
                }
                for i in range(3)
            ],
        }
    return report


@pytest.fixture
def no_inventory(monkeypatch):
    monkeypatch.setattr(campaign, "environment_info", lambda: {"fixture": True})
    monkeypatch.setattr(campaign, "capture_inventory", lambda *_: {"fixture": True})


def test_offline_plan_has_no_runtime_imports_and_writes_no_files(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from omnismi.cli import main; "
            "assert main(['self-test','campaign','--plan','--target','rtx-5090',"
            "'--suite','acceptance']) == 0; "
            "assert not {'torch','jax','numpy'} & set(sys.modules)",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).parents[1] / "src")},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["executed"] is False and report["status"] == "INCONCLUSIVE"
    assert report["physical_unit_coverage"] == "UNKNOWN"
    assert report["known_fault_detection"] == "NOT_ASSESSED"
    assert len(report["stages"]) == 6
    assert report["stage_timeout_budget_seconds"] == 3840
    assert list(tmp_path.iterdir()) == []


def test_sequence_replays_inputs_in_independent_runs():
    selected = campaign.stages("tpu-v6e", "acceptance", seed=2**32 - 1)
    assert selected[1][1] == selected[2][1]
    assert selected[3][1].seed == 0
    assert selected[4][1].profile == "soak"
    assert selected[-1][1].profile == "smoke"
    assert len(campaign.stages("b300")) == 1
    with pytest.raises(ValueError, match="power target"):
        campaign.stages("b300", power_target_w=500)
    with pytest.raises(ValueError, match="exceed"):
        campaign.stages("b300", "acceptance", stage_timeout=300, duration=300)
    for kwargs in ({"stage_timeout": float("inf")}, {"seed": -1}, {"device": -1}):
        with pytest.raises(ValueError):
            campaign.stages("b300", **kwargs)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(executed=False),
        lambda r: r.update(complete=False),
        lambda r: r.update(synthetic_demo=True),
        lambda r: r.update(schema_version=2),
        lambda r: r["config"].update(seed=24),
        lambda r: r["cases"].pop(),
        lambda r: r["results"].pop(),
        lambda r: r["results"][-1].update(comparisons=2, executions=1),
        lambda r: r["results"].append(r["results"][0]),
        lambda r: r["results"][0].update(comparisons=0),
        lambda r: r["results"][0].update(comparisons=2, executions=1),
        lambda r: r["results"][0].update(status="INCONCLUSIVE"),
        lambda r: r["identity"].update(name="NVIDIA H100"),
        lambda r: r["identity"].update(runtime_device_index=1),
        lambda r: r["identity"].update(framework="unverified"),
        lambda r: r["acceptance_gates"].update(power_target=False),
        lambda r: r["acceptance_gates"].update(future_gate=False),
        lambda r: r["errors"].append({"reason": "worker_timeout"}),
    ],
)
def test_pass_never_hides_incomplete_or_foreign_evidence(mutate):
    config = campaign.stages("rtx-5090")[0][1]
    report = passed_report(config)
    assert campaign.assess(report, config) == ("PASS", [])
    mutate(report)
    assert campaign.assess(report, config)[0] == "INCONCLUSIVE"


def test_mismatch_survives_raw_pass_and_post_failure_timeout():
    config = campaign.stages("rtx-5090")[0][1]
    report = passed_report(config)
    report["results"][0]["status"] = "FAIL"
    report["errors"].append({"reason": "worker_timeout"})
    assert campaign.assess(report, config)[0] == "FAIL"
    report["synthetic_demo"] = True
    assert campaign.assess(report, config)[0] == "INCONCLUSIVE"


def test_load_and_power_claims_need_comparisons_postchecks_and_samples():
    config = campaign.stages("b300", "acceptance", power_target_w=700)[4][1]
    report = passed_report(config)
    assert campaign.assess(report, config)[0] == "PASS"
    for mutate in (
        lambda r: r.update(load_seconds=0),
        lambda r: r["results"].pop(),
        lambda r: r["results"][-1].update(comparisons=2, executions=1),
        lambda r: r["results"][0].update(phases=["baseline"]),
        lambda r: r["telemetry"].update(samples=[]),
        lambda r: r["telemetry"].update(attribution="no_matching_runtime_uuid"),
        lambda r: r["telemetry"]["samples"][0].update(power_w=0),
        lambda r: r["telemetry"]["samples"][0].update(timestamp_ns=2),
        lambda r: r["identity"].update(uuid=None),
    ):
        altered = copy.deepcopy(report)
        mutate(altered)
        assert campaign.assess(altered, config)[0] == "INCONCLUSIVE"


def test_success_archives_every_stage_and_checksums(tmp_path, no_inventory):
    selected = campaign.stages("rtx-5090", "acceptance")
    output = tmp_path / "card-a"
    report = campaign.execute(selected, "acceptance", output, worker=passed_report)
    assert report["status"] == "PASS" and report["complete"] is True
    assert report["identity_continuity"] == "UUID"
    assert report["power_validation"] == "NOT_REQUESTED"
    assert report["physical_unit_coverage"] == "UNKNOWN"
    assert report["hardware_fault_confirmed"] is False
    hashes = json.loads((output / "checksums.json").read_text())["files"]
    assert len([h for h in hashes if h["path"].endswith("report.json")]) == 6
    for item in hashes:
        assert campaign.fingerprint(output / item["path"]) == item["sha256"]
    with tarfile.open(output.with_name("card-a.tar.gz")) as archive:
        assert "card-a/campaign.json" in archive.getnames()
        assert "card-a/checksums.json" in archive.getnames()
    with pytest.raises(ValueError, match="archive already exists"):
        campaign.execute(selected, "acceptance", output, worker=passed_report)


@pytest.mark.parametrize(
    "failure", ["FAIL", "INCONCLUSIVE", "exception", "interrupt", "identity"]
)
def test_nonpass_stops_later_load_and_preserves_completed_stages(
    tmp_path, no_inventory, failure
):
    calls = []

    def worker(config):
        calls.append(config)
        report = passed_report(config)
        if len(calls) == 2:
            if failure == "exception":
                raise OSError("fixture error")
            if failure == "interrupt":
                raise KeyboardInterrupt()
            if failure == "identity":
                report["identity"]["uuid"] = "fixture-device-b"
            else:
                report["status"] = failure
        return report

    result = campaign.execute(
        campaign.stages("b300", "acceptance"),
        "acceptance",
        tmp_path / "card",
        worker=worker,
    )
    assert len(calls) == 2
    assert result["status"] == ("FAIL" if failure == "FAIL" else "INCONCLUSIVE")
    assert result["complete"] is False
    assert result["stages"][0]["status"] == "PASS"
    assert result["stages"][2]["status"] == "NOT_RUN"
    if failure == "identity":
        assert result["stages"][1]["reasons"] == ["device_or_runtime_changed"]


def test_failure_is_preserved_when_report_write_fails(
    tmp_path, no_inventory, monkeypatch
):
    writer = campaign.write_json

    def fail_report(path, value):
        if path.name == "report.json":
            raise OSError("fixture disk write failure")
        writer(path, value)

    def worker(config):
        report = passed_report(config)
        report["status"] = "FAIL"
        return report

    monkeypatch.setattr(campaign, "write_json", fail_report)
    report = campaign.execute(
        campaign.stages("b300"), "pilot", tmp_path / "card", worker=worker
    )
    assert report["status"] == "FAIL"
    assert report["errors"][0]["reason"] == "OSError"


def test_tpu_does_not_invent_physical_identity(tmp_path, no_inventory):
    report = campaign.execute(
        campaign.stages("tpu-v6e"), "pilot", tmp_path / "tpu", worker=passed_report
    )
    assert report["status"] == "PASS"
    assert report["identity_continuity"] == "RUNTIME_ONLY"


def test_existing_directory_never_overwritten(tmp_path, no_inventory):
    (tmp_path / "keep.txt").write_text("keep")
    with pytest.raises(FileExistsError):
        campaign.execute(
            campaign.stages("b300"), "pilot", tmp_path, worker=passed_report
        )
    assert (tmp_path / "keep.txt").read_text() == "keep"


def test_run_requires_an_explicit_output_directory(capsys):
    assert run(["campaign", "--run", "--target", "b300"]) == 64
    assert "requires --output-dir" in capsys.readouterr().out


def test_sigterm_stops_campaign_and_restores_handler(tmp_path, no_inventory):
    previous = signal.getsignal(signal.SIGTERM)

    def interrupted_worker(config):
        os.kill(os.getpid(), signal.SIGTERM)
        pytest.fail("SIGTERM must interrupt the worker")

    with campaign.termination_handler():
        report = campaign.execute(
            campaign.stages("b300"),
            "pilot",
            tmp_path / "card",
            worker=interrupted_worker,
        )
    assert signal.getsignal(signal.SIGTERM) == previous
    assert report["status"] == "INCONCLUSIVE" and report["complete"] is False
    assert report["errors"][0]["detail"] == "SIGTERM"
    assert report["stages"][0]["status"] == "INCONCLUSIVE"
    assert (tmp_path / "card.tar.gz").is_file()


@pytest.mark.parametrize("stage_index", [0, 4])
def test_engine_reports_satisfy_campaign_contract(stage_index):
    """Exercise actual engine serialization; the backend is a CPU oracle fixture."""
    import numpy as np

    from omnismi.selftest.engine import execute
    from omnismi.selftest.reference import expected

    config = campaign.stages("tpu-v6e", "acceptance", memory_mib=16, duration=0.01)[
        stage_index
    ][1]

    class OracleBackend:
        identity = passed_report(config)["identity"]

        def execute(self, case, a, b):
            value, indices = expected(case, a, b), None
            if case.operator in ("sort", "topk"):
                indices = np.argsort(a, axis=-1)
                if case.operator == "topk":
                    if case.largest:
                        indices = indices[:, ::-1]
                    indices = indices[:, : case.k]
            return value, indices

    report = campaign.canonical(
        execute(config, lambda _: None, backend=OracleBackend())
    )
    assert campaign.assess(report, config) == ("PASS", [])


def test_cancelled_worker_keeps_failure_checkpoint_and_reaps_group(monkeypatch):
    from omnismi.selftest import runner

    config = campaign.stages("b300")[0][1]
    killed = []

    class CancelledProcess:
        pid, returncode = 123456, -9

        def __init__(self, command, **kwargs):
            report = passed_report(config)
            report.update(status="FAIL", complete=False)
            Path(command[-1]).write_text(json.dumps(report))
            assert kwargs["start_new_session"] is True

        def wait(self, timeout=None):
            if timeout is not None:
                raise KeyboardInterrupt()
            return self.returncode

    monkeypatch.setattr(runner.subprocess, "Popen", CancelledProcess)
    monkeypatch.setattr(runner.os, "killpg", lambda *args: killed.append(args))
    report = runner.run(config)
    assert killed == [(123456, signal.SIGKILL)]
    assert report["status"] == "FAIL" and report["complete"] is False
    assert report["errors"][0]["reason"] == "worker_cancelled"
