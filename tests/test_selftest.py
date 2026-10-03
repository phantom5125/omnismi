"""SDC fault injection and conservative verdict/coverage contracts."""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pytest

from omnismi.selftest.catalog import Case, Config, cases, plan
from omnismi.selftest.engine import execute
from omnismi.selftest.reference import compare, expected, fingerprint, inputs, quantize
from omnismi.selftest.runner import finish, read_checkpoint
from omnismi.selftest.telemetry import Sampler


class OracleBackend:
    identity = {"vendor": "test", "uuid": None, "multiprocessor_count": 132}

    def execute(self, case, a, b):
        value = expected(case, a, b)
        indices = None
        if case.operator in ("sort", "topk"):
            indices = np.argsort(a, axis=-1)
            if case.operator == "topk":
                if case.largest:
                    indices = indices[:, ::-1]
                indices = indices[:, : case.k]
        return value, indices


def test_plan_is_deterministic_and_preserves_topk_independence():
    config = Config("nvidia", profile="extended")
    assert plan(config) == plan(config)
    selected = cases(config)
    assert len({case.id for case in selected}) == len(selected)
    topk = [case for case in selected if case.operator == "topk"]
    assert {case.dtype for case in topk} == {"float32", "float16", "bfloat16", "int32"}
    assert {case.layout for case in topk} == {"strided", "contiguous"}
    assert {case.largest for case in topk} == {True, False}
    assert any(case.k == case.shape[-1] for case in topk)
    assert all(
        case.layout == "contiguous" for case in cases(replace(config, vendor="google"))
    )


@pytest.mark.parametrize(
    "change",
    [
        {"seed": -1},
        {"passes": 0},
        {"timeout": float("nan")},
        {"timeout": 3601},
        {"memory_mib": 0},
        {"operators": ()},
        {"operators": ("bogus",)},
        {"operators": ("copy", "copy")},
        {"device": True},
        {"power_target_w": 300},
        {"profile": "soak", "power_target_w": float("inf")},
    ],
)
def test_reject_invalid_budgets(change):
    with pytest.raises(ValueError):
        replace(Config("nvidia"), **change).validate()


def test_seed_and_input_digest_are_reproducible():
    case = Case("0000-topk", "topk", (7, 257))
    a, b = inputs(case, 2)
    assert fingerprint(a, b) == fingerprint(*inputs(case, 2))
    assert fingerprint(a, b) != fingerprint(*inputs(case, 3))


def test_bfloat16_rounds_ties_to_even():
    np.testing.assert_array_equal(
        quantize([1 + 2**-8, 1 + 3 * 2**-8], "bfloat16"), [1, 1 + 2**-6]
    )


def test_topk_tied_indices_and_unsorted_permutations_are_legal():
    case = Case("0000-topk", "topk", (1, 5), k=3, sorted=False)
    a = np.array([[1, 9, 9, 9, 3]], dtype=np.float32)
    reference = expected(case, a, a)
    assert (
        compare(case, a, reference, np.array([[9, 9, 9]]), np.array([[3, 1, 2]]))[
            "status"
        ]
        == "PASS"
    )
    case = replace(case, k=4)
    reference = expected(case, a, a)
    assert (
        compare(case, a, reference, np.array([[9, 3, 9, 9]]), np.array([[3, 4, 1, 2]]))[
            "status"
        ]
        == "PASS"
    )


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("value", "value_index_disagreement"),
        ("duplicate", "duplicate_indices"),
        ("index", "index_out_of_bounds"),
        ("nan", "nonfinite_output"),
        ("inf", "nonfinite_output"),
        ("shape", "output_shape_mismatch"),
        ("missing", "missing_indices"),
        ("wrong_selection", "cpu_reference_mismatch"),
    ],
)
def test_topk_faults_are_detected(mutation, reason):
    case = Case("0000-topk", "topk", (1, 5), k=2)
    a = np.array([[1, 2, 3, 4, 5]], dtype=np.float32)
    reference = expected(case, a, a)
    actual, indices = reference.copy(), np.array([[4, 3]])
    if mutation == "value":
        actual[0, 0] += 1
    elif mutation == "duplicate":
        indices[0, 1] = indices[0, 0]
    elif mutation == "index":
        indices[0, 0] = 5
    elif mutation in ("nan", "inf"):
        actual[0, 0] = float(mutation)
    elif mutation == "shape":
        actual = actual[:, :1]
    elif mutation == "missing":
        indices = None
    elif mutation == "wrong_selection":
        actual, indices = np.array([[3, 2]]), np.array([[2, 1]])
    result = compare(case, a, reference, actual, indices)
    assert result["status"] == "FAIL"
    assert result["reason"] == reason


def test_sort_pass_does_not_mask_topk_failure_and_artifacts_reproduce(tmp_path):
    class BadTopK(OracleBackend):
        def execute(self, case, a, b):
            actual, indices = super().execute(case, a, b)
            if case.operator == "topk":
                actual.flat[0] += 1
            return actual, indices

    checkpoints = []
    report = execute(
        Config("nvidia", operators=("sort", "topk"), artifact_dir=str(tmp_path)),
        lambda value: checkpoints.append(json.loads(json.dumps(value))),
        backend=BadTopK(),
    )
    assert report["status"] == "FAIL"
    assert report["results"][0]["status"] == "PASS"
    failure = report["failures"][0]
    assert not failure["hardware_fault_confirmed"]
    assert any(item["status"] == "FAIL" for item in checkpoints)
    case = Case(**failure["case"])
    with np.load(failure["artifact"], allow_pickle=False) as data:
        assert fingerprint(data["a"], data["b"]) == failure["input_sha256"]
        assert (
            compare(case, data["a"], data["expected"], data["actual"], data["indices"])[
                "status"
            ]
            == "FAIL"
        )


def test_pass_does_not_certify_physical_units():
    report = execute(Config("nvidia"), lambda _: None, backend=OracleBackend())
    assert report["status"] == "PASS"
    assert report["coverage"]["completed_cases"] == report["coverage"]["planned_cases"]
    assert report["coverage"]["physical_units"] == {
        "status": "UNKNOWN",
        "observed_ids": [],
        "expected_count": 132,
    }
    assert report["current_hardware_health"] == "INCONCLUSIVE"
    report = execute(
        Config("nvidia", require_unit_coverage=True),
        lambda _: None,
        backend=OracleBackend(),
    )
    assert report["status"] == "INCONCLUSIVE"


def test_runtime_error_is_inconclusive_not_sdc():
    class Unavailable(OracleBackend):
        def execute(self, *args):
            raise RuntimeError("operator unsupported")

    report = execute(Config("nvidia"), lambda _: None, backend=Unavailable())
    assert report["status"] == "INCONCLUSIVE"
    assert not report["failures"]
    assert report["coverage"]["completed_cases"] == 0


def test_budget_rejection_never_executes(monkeypatch):
    monkeypatch.setattr(
        "omnismi.selftest.engine.cases",
        lambda _: [Case("0000-copy", "copy", (8192, 8192))],
    )
    report = execute(
        Config("nvidia", memory_mib=16), lambda _: None, backend=OracleBackend()
    )
    assert report["status"] == "INCONCLUSIVE"
    assert report["results"][0]["reason"] == "tensor_budget_exceeded"
    assert report["results"][0]["executions"] == 0


def test_timeout_preserves_numerical_failure():
    report = plan(Config("nvidia"))
    report["status"] = "FAIL"
    assert finish(report, interrupted=True, returncode=-9)["status"] == "FAIL"
    assert not report["complete"]
    assert finish(plan(Config("nvidia")), interrupted=True)["status"] == "INCONCLUSIVE"


def test_corrupt_checkpoint_cannot_pass(tmp_path):
    fallback = plan(Config("nvidia"))
    target = tmp_path / "report.json"
    target.write_text('{"status":"PASS", "complete":true}')
    assert read_checkpoint(target, fallback)["status"] == "INCONCLUSIVE"


@pytest.mark.parametrize("status", ["FAIL", "INCONCLUSIVE"])
def test_real_subprocess_timeout_preserves_checkpoint(monkeypatch, status):
    import subprocess
    import sys

    from omnismi.selftest import runner

    real_popen = subprocess.Popen

    def checkpoint_then_hang(command, **kwargs):
        source = (
            "import json,sys,time; from pathlib import Path; "
            "from omnismi.selftest.catalog import Config,plan; "
            "r=plan(Config(**json.loads(sys.argv[1]))); "
            f"r['status']={status!r}; "
            "Path(sys.argv[2]).write_text(json.dumps(r)); time.sleep(30)"
        )
        return real_popen(
            [sys.executable, "-c", source, command[-2], command[-1]], **kwargs
        )

    monkeypatch.setattr(runner.subprocess, "Popen", checkpoint_then_hang)
    report = runner.run(Config("nvidia", timeout=1))
    assert report["status"] == status
    assert report["errors"][-1]["reason"] == "worker_timeout"
    assert report["errors"][-1]["returncode"] == -9


def test_public_ppu_run_is_explicitly_inconclusive(capsys):
    from omnismi.cli import main

    assert main(["self-test", "--run", "--vendor", "alibaba"]) == 3
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "INCONCLUSIVE"
    assert report["coverage"]["completed_cases"] == 0
    assert "SAIL" in report["errors"][0]["detail"]


def test_deadline_progress_retains_completed_cases(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("omnismi.selftest.engine.time.monotonic", lambda: clock[0])

    class TimedBackend(OracleBackend):
        def execute(self, case, a, b):
            clock[0] += 10
            return super().execute(case, a, b)

    checkpoints = []
    report = execute(
        Config("nvidia", timeout=5),
        lambda value: checkpoints.append(json.loads(json.dumps(value))),
        backend=TimedBackend(),
    )
    assert report["status"] == "INCONCLUSIVE"
    assert report["coverage"]["completed_cases"] == 1
    assert any(item["coverage"]["completed_cases"] == 1 for item in checkpoints)


def test_power_gate_requires_fresh_attributed_load_samples():
    sampler = Sampler({"uuid": None})
    sampler.start()
    assert sampler._thread is None
    assert not sampler.report(300)["target_observed"]
    sampler.samples = [{"power_w": 500, "phase": "baseline"}] * 5
    assert not sampler.report(300)["target_observed"]
    sampler.samples += [{"power_w": 310, "phase": "load"}] * 3
    assert sampler.report(300)["target_observed"]
    sampler.samples += [{"power_w": 100, "phase": "load"}] * 3
    assert not sampler.report(300)["target_observed"]


def test_soak_checks_each_load_and_rechecks(monkeypatch):
    # Deterministic clock avoids long tests while exercising the complete loop.
    clock = [0.0]
    monkeypatch.setattr("omnismi.selftest.engine.time.monotonic", lambda: clock[0])

    class TimedBackend(OracleBackend):
        def execute(self, case, a, b):
            clock[0] += 1
            return super().execute(case, a, b)

    report = execute(
        Config(
            "nvidia",
            profile="soak",
            operators=("matmul",),
            memory_mib=16,
            duration=3,
            timeout=600,
        ),
        lambda _: None,
        backend=TimedBackend(),
    )
    assert report["status"] == "PASS"
    load = next(
        item for item in report["results"] if item["case"]["id"] == "9000-matmul-load"
    )
    assert load["comparisons"] == load["executions"] == 3
    assert report["load_duration_completed"]
    assert "post_load" in report["results"][0]["phases"]
