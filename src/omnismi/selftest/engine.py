"""Checkpointed comparisons and an optional bounded, interleaved load phase."""

from __future__ import annotations

import math
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from .catalog import Case, cases, plan


def execute(config, checkpoint, *, backend=None, sampler=None):
    import numpy as np

    from .backends import connect
    from .reference import compare, expected, fingerprint, inputs
    from .telemetry import Sampler

    started = time.monotonic()
    report = plan(config)
    report.update(
        executed=True, phase="initializing", results=[], failures=[], errors=[]
    )
    report["reference_environment"] = {
        "numpy_version": np.__version__,
        "python_version": sys.version.split()[0],
        "input_generator": "numpy.default_rng/PCG64",
        "catalog_version": 1,
    }
    checkpoint(report)
    try:
        backend = backend or connect(config)
    except Exception as exc:
        report["errors"].append(
            {"reason": "runtime_unavailable", "detail": str(exc)[:1000]}
        )
        checkpoint(report)
        return report
    report["identity"] = backend.identity
    report["coverage"]["physical_units"]["expected_count"] = backend.identity.get(
        "multiprocessor_count"
    )
    sampler = sampler or Sampler(backend.identity)
    sampler.start()
    selected = cases(config)
    records = {}
    deadline = started + config.timeout
    budget = config.memory_mib * 1024 * 1024
    failed = False

    def save():
        report["results"] = list(records.values())
        report["coverage"]["completed_cases"] = sum(
            1
            for case in selected
            if case.id in records
            and records[case.id]["comparisons"] >= config.passes
            and records[case.id]["status"] == "PASS"
        )
        report["coverage"]["comparison_count"] = sum(
            item["comparisons"] for item in records.values()
        )
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        report["telemetry"] = sampler.report(config.power_target_w)
        checkpoint(report)

    def run_case(case, iteration, phase, cached=None):
        nonlocal failed
        if time.monotonic() >= deadline:
            raise TimeoutError("self-test deadline reached")
        report["phase"] = sampler.phase = phase
        seed = (
            config.seed + int(case.id.split("-")[0]) * 1009 + iteration * 9176
        ) % 2**32
        record = records.setdefault(
            case.id,
            {
                "case": asdict(case),
                "status": "PASS",
                "executions": 0,
                "comparisons": 0,
                "phases": [],
            },
        )
        if phase not in record["phases"]:
            record["phases"].append(phase)
        if case.estimated_device_bytes > budget:
            record.update(status="INCONCLUSIVE", reason="tensor_budget_exceeded")
            save()
            return
        record["executions"] += 1
        record.update(last_seed=seed, last_iteration=iteration)
        try:
            if cached is None:
                a, b = inputs(case, seed)
                reference = expected(case, a, b)
            else:
                a, b, reference, seed = cached
                record["last_seed"] = seed
            actual, indices = backend.execute(case, a, b)
            outcome = compare(case, a, reference, actual, indices)
            record["comparisons"] += 1
            record["last_comparison"] = outcome
            if outcome["status"] == "FAIL":
                record["status"] = report["status"] = "FAIL"
                failed = True
                failure = {
                    "classification": "numerical_mismatch_candidate_sdc",
                    "case": asdict(case),
                    "seed": seed,
                    "iteration": iteration,
                    "phase": phase,
                    "input_sha256": fingerprint(a, b),
                    **outcome,
                    "hardware_fault_confirmed": False,
                }
                # Commit the numerical failure BEFORE attempting optional I/O.
                report["failures"].append(failure)
                save()
                if config.artifact_dir:
                    try:
                        directory = Path(config.artifact_dir)
                        directory.mkdir(parents=True, exist_ok=True)
                        artifact = directory / f"{case.id}-{uuid.uuid4().hex}.npz"
                        with artifact.open("xb") as stream:
                            np.savez_compressed(
                                stream,
                                a=a,
                                b=b,
                                expected=reference,
                                actual=actual,
                                indices=[] if indices is None else indices,
                            )
                        failure["artifact"] = str(artifact.resolve())
                    except Exception as exc:
                        failure["artifact_error"] = str(exc)[:500]
        except Exception as exc:
            # Runtime/SDK/allocation errors are not proof of a numerical mismatch.
            if record["status"] != "FAIL":
                record.update(
                    status="INCONCLUSIVE",
                    reason="execution_error",
                    detail=str(exc)[:1000],
                )
        save()

    try:
        for iteration in range(config.passes):
            for case in selected:
                run_case(case, iteration, "baseline")
                if failed:
                    break
            if failed:
                break
        if config.profile == "soak" and not failed:
            # Large dense GEMMs, each downloaded and checked. CPU comparison and
            # topk rechecks introduce gaps; sustained power must be observed.
            side = max(256, min(2048, int(math.sqrt(budget / 64)) // 256 * 256))
            load = Case("9000-matmul-load", "matmul", (side, side), dtype="float16")
            a, b = inputs(load, config.seed)
            reference = expected(load, a, b)
            cached = (a, b, reference, config.seed)
            report["load_case"] = asdict(load)
            load_start = time.monotonic()
            load_iteration = 0
            while time.monotonic() - load_start < config.duration and not failed:
                run_case(load, load_iteration, "load", cached)
                if records[load.id]["status"] != "PASS":
                    break
                # Check topk between bursts to exercise a distinct kernel family.
                if load_iteration % 4 == 3:
                    for case in selected:
                        if case.operator == "topk":
                            run_case(case, config.passes + load_iteration, "recheck")
                            if failed:
                                break
                load_iteration += 1
            report["load_seconds"] = round(time.monotonic() - load_start, 3)
            report["load_duration_completed"] = (
                report["load_seconds"] >= config.duration
            )
            if not failed:
                for case in selected:
                    run_case(case, config.passes + load_iteration + 1, "post_load")
                    if failed:
                        break
        report["complete"] = not failed
    except TimeoutError as exc:
        report["errors"].append({"reason": "deadline_exceeded", "detail": str(exc)})
    except Exception as exc:
        report["errors"].append({"reason": "worker_error", "detail": str(exc)[:1000]})
    finally:
        sampler.stop()
        telemetry = sampler.report(config.power_target_w)
        gates = {
            "all_requested_comparisons": report["complete"]
            and not report["errors"]
            and len(records) >= len(selected)
            and all(item["status"] == "PASS" for item in records.values()),
            "load_duration": config.profile != "soak"
            or report.get("load_duration_completed", False),
            "power_target": config.power_target_w is None
            or telemetry["target_observed"] is True,
            "physical_unit_coverage": not config.require_unit_coverage,
        }
        report["acceptance_gates"] = gates
        report["status"] = (
            "FAIL" if failed else ("PASS" if all(gates.values()) else "INCONCLUSIVE")
        )
        report["phase"] = "finished"
        save()
    return report
