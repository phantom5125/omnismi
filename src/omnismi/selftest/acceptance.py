"""Portable, bounded acceptance campaigns; never provisions cloud resources."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import signal
import subprocess
import sys
import tarfile
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from .catalog import Config, plan
from .targets import matches_target, target_catalog, target_profile

EXIT_CODES = {"PASS": 0, "FAIL": 2, "INCONCLUSIVE": 3}
IDENTITY_FIELDS = (
    "vendor",
    "name",
    "uuid",
    "runtime_device_index",
    "execution_device",
    "framework",
    "framework_version",
    "runtime_version",
)
VISIBILITY_FIELDS = (
    "CUDA_VISIBLE_DEVICES",
    "NVIDIA_VISIBLE_DEVICES",
    "HIP_VISIBLE_DEVICES",
    "ROCR_VISIBLE_DEVICES",
    "GPU_DEVICE_ORDINAL",
    "TPU_VISIBLE_DEVICES",
    "TPU_VISIBLE_CHIPS",
    "JAX_PLATFORMS",
)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.loads(json.dumps(value, allow_nan=False))


def stages(
    target,
    suite="pilot",
    *,
    device=0,
    seed=42,
    memory_mib=256,
    stage_timeout=900,
    duration=300,
    power_target_w=None,
):
    """Fixed sequence: independent workers, same-seed replay, new seed, load."""
    if suite not in ("pilot", "acceptance"):
        raise ValueError("suite must be pilot or acceptance")
    base = Config(
        target_profile(target)["vendor"],
        target=target,
        device=device,
        seed=seed,
        memory_mib=memory_mib,
        timeout=stage_timeout,
        duration=duration,
    )
    base.validate()
    result = [("01-smoke", replace(base, timeout=min(stage_timeout, 120)))]
    if suite == "pilot":
        if power_target_w is not None:
            raise ValueError("a power target requires the acceptance suite")
        return result
    if duration >= stage_timeout:
        raise ValueError("stage-timeout must exceed load duration")
    result.extend(
        [
            ("02-extended", replace(base, profile="extended")),
            ("03-repeat", replace(base, profile="extended")),
            ("04-new-seed", replace(base, profile="extended", seed=(seed + 1) % 2**32)),
            ("05-load", replace(base, profile="soak", power_target_w=power_target_w)),
            ("06-post-smoke", replace(base, timeout=min(stage_timeout, 120))),
        ]
    )
    for _, config in result:
        config.validate()
    return result


def campaign_plan(selected, suite):
    from omnismi import __version__

    return {
        "schema_version": 1,
        "report_type": "hardware_acceptance",
        "tool_version": __version__,
        "suite": suite,
        "status": "INCONCLUSIVE",
        "executed": False,
        "complete": False,
        "stage_timeout_budget_seconds": sum(config.timeout for _, config in selected),
        "physical_unit_coverage": "UNKNOWN",
        "hardware_fault_confirmed": False,
        "current_hardware_health": "INCONCLUSIVE",
        "known_fault_detection": "NOT_ASSESSED",
        "power_validation": (
            "NOT_RUN"
            if any(config.power_target_w is not None for _, config in selected)
            else "NOT_REQUESTED"
        ),
        "stages": [
            {
                "id": name,
                "status": "NOT_RUN",
                "config": asdict(config),
                "planned_cases": len(plan(config)["cases"]),
            }
            for name, config in selected
        ],
        "limitations": [
            "PASS applies to this suite on the reported runtime-visible device only.",
            "Healthy-card screening does not measure sensitivity to real SDC.",
            "Operator results do not prove physical-unit or full-memory coverage.",
            "Time budgets exclude provisioning, metadata and evidence I/O; "
            "finishing a campaign does not stop cloud billing.",
            "No XID/RAS logs are collected; absent logs do not prove no events.",
            "A killed campaign or a RUNNING stage is incomplete, never PASS.",
        ],
    }


def identity_key(identity):
    return {key: identity.get(key) for key in IDENTITY_FIELDS}


def assess(report, config, baseline=None):
    """Conservative acceptance: a raw PASS cannot hide skipped or stale cases."""
    if not isinstance(report, dict):
        return "INCONCLUSIVE", ["invalid_report"]
    if (
        report.get("report_type") != "hardware_selftest"
        or report.get("schema_version") != 1
        or report.get("synthetic_demo")
    ):
        return "INCONCLUSIVE", ["invalid_or_synthetic_report"]
    records = report.get("results", [])
    if (
        report.get("status") == "FAIL"
        or report.get("failures")
        or (
            isinstance(records, list)
            and any(isinstance(r, dict) and r.get("status") == "FAIL" for r in records)
        )
    ):
        return "FAIL", ["numerical_mismatch_observed"]
    reasons = []
    expected = canonical(plan(config))
    if (
        report.get("config") != expected["config"]
        or report.get("cases") != expected["cases"]
    ):
        reasons.append("plan_mismatch")
    if (
        report.get("status") != "PASS"
        or report.get("executed") is not True
        or report.get("complete") is not True
        or report.get("errors")
    ):
        reasons.append("incomplete_or_unsuccessful_run")
    identity = report.get("identity")
    if not isinstance(identity, dict) or not matches_target(config.target, identity):
        reasons.append("target_identity_unverified")
    elif identity.get("runtime_device_index") != config.device:
        reasons.append("runtime_index_mismatch")
    elif baseline is not None and identity_key(identity) != baseline:
        reasons.append("device_or_runtime_changed")
    if isinstance(identity, dict) and (
        identity.get("framework") != ("jax" if config.vendor == "google" else "pytorch")
        or not identity.get("framework_version")
    ):
        reasons.append("runtime_identity_unverified")
    gates = report.get("acceptance_gates", {})
    if isinstance(gates, dict) and any(value is not True for value in gates.values()):
        reasons.append("unmet_acceptance_gate")
    for gate in (
        "all_requested_comparisons",
        "load_duration",
        "power_target",
        "physical_unit_coverage",
    ):
        if not isinstance(gates, dict) or gates.get(gate) is not True:
            reasons.append(f"gate_not_met:{gate}")
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        reasons.append("invalid_case_records")
    else:
        by_id = {}
        for record in records:
            case = record.get("case")
            key = case.get("id") if isinstance(case, dict) else None
            if not isinstance(key, str) or key in by_id:
                reasons.append("invalid_or_duplicate_case")
                continue
            by_id[key] = record
        for case in expected["cases"]:
            record = by_id.pop(case["id"], {})
            comparisons, executions = record.get("comparisons"), record.get(
                "executions"
            )
            if (
                record.get("case") != case
                or record.get("status") != "PASS"
                or type(comparisons) is not int
                or type(executions) is not int
                or not config.passes <= comparisons <= executions
            ):
                reasons.append("missing_or_incomplete_comparisons")
                break
        if config.profile == "soak":
            load = by_id.pop("9000-matmul-load", {})
            if (
                load.get("status") != "PASS"
                or type(load.get("comparisons")) is not int
                or type(load.get("executions")) is not int
                or not 1 <= load["comparisons"] <= load["executions"]
                or load.get("case", {}).get("operator") != "matmul"
                or report.get("load_duration_completed") is not True
                or not isinstance(report.get("load_seconds"), (int, float))
                or not math.isfinite(report["load_seconds"])
                or report["load_seconds"] < config.duration
            ):
                reasons.append("load_incomplete")
            if any(
                not isinstance(record.get("phases"), list)
                or "post_load" not in record["phases"]
                for record in records
                if isinstance(record.get("case"), dict)
                and record["case"].get("id") != "9000-matmul-load"
            ):
                reasons.append("post_load_checks_missing")
        if by_id:
            reasons.append("unexpected_case_records")
    if config.power_target_w is not None:
        telemetry = report.get("telemetry", {})
        if (
            not isinstance(telemetry, dict)
            or telemetry.get("target_observed") is not True
            or telemetry.get("target_w") != config.power_target_w
            or telemetry.get("attribution") != "matched_runtime_uuid"
        ):
            reasons.append("power_evidence_missing")
        samples = telemetry.get("samples", []) if isinstance(telemetry, dict) else []
        samples = samples if isinstance(samples, list) else []
        load_samples = [
            s for s in samples if isinstance(s, dict) and s.get("phase") == "load"
        ]
        valid = [
            s
            for s in load_samples
            if type(s.get("timestamp_ns")) is int
            and s["timestamp_ns"] > 0
            and isinstance(s.get("power_w"), (int, float))
            and math.isfinite(s["power_w"])
            and s["power_w"] >= 0
        ]
        if (
            not isinstance(identity, dict)
            or not identity.get("uuid")
            or len(valid) < 3
            or len(valid) != len(load_samples)
            or len({s["timestamp_ns"] for s in valid}) != len(valid)
            or sum(s["power_w"] >= config.power_target_w for s in valid)
            < 0.8 * len(valid)
        ):
            reasons.append("power_samples_insufficient")
    return ("INCONCLUSIVE", sorted(set(reasons))) if reasons else ("PASS", [])


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def environment_info():
    import omnismi

    versions = {}
    for package in (
        "omnismi",
        "numpy",
        "torch",
        "torch-mlu",
        "jax",
        "jaxlib",
        "libtpu",
        "nvidia-ml-py",
        "amdsmi",
    ):
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    package_path = Path(omnismi.__file__).resolve()
    checkout = package_path.parents[2]
    source = {"package_path": str(package_path), "git_commit": None, "git_dirty": None}
    # Associate a revision only with the actually imported source checkout.
    if (checkout / "pyproject.toml").is_file() and (checkout / ".git").exists():
        try:
            source["git_commit"] = subprocess.check_output(
                ["git", "-C", str(checkout), "rev-parse", "HEAD"],
                timeout=5,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            source["git_dirty"] = bool(
                subprocess.check_output(
                    ["git", "-C", str(checkout), "status", "--porcelain"],
                    timeout=5,
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
            )
        except (OSError, subprocess.SubprocessError):
            pass
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "versions": versions,
        "source": source,
        "visibility": {
            key: os.environ[key] for key in VISIBILITY_FIELDS if key in os.environ
        },
    }


def capture_inventory(directory, label):
    """Management inventory is context, never ordinal-matched to the test device."""
    stdout, stderr = directory / f"{label}.json", directory / f"{label}.stderr.txt"
    with stdout.open("wb") as out, stderr.open("wb") as err:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "omnismi", "-o", "json"],
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                timeout=15,
                check=False,
            )
            return {
                "returncode": result.returncode,
                "stdout": stdout.name,
                "stderr": stderr.name,
            }
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "error": type(exc).__name__,
                "stdout": stdout.name,
                "stderr": stderr.name,
            }


def seal(directory):
    entries = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise OSError("Evidence bundle cannot contain symlinks")
        if path.is_file() and path != directory / "checksums.json":
            entries.append(
                {
                    "path": path.relative_to(directory).as_posix(),
                    "sha256": fingerprint(path),
                }
            )
    write_json(directory / "checksums.json", {"algorithm": "sha256", "files": entries})
    archive = directory.with_name(directory.name + ".tar.gz")
    if archive.exists():
        raise FileExistsError("archive already exists")
    temporary = archive.with_suffix(archive.suffix + ".partial")
    with (
        temporary.open("xb") as stream,
        tarfile.open(fileobj=stream, mode="w:gz") as tar,
    ):
        tar.add(directory, arcname=directory.name)
    temporary.rename(archive)
    return archive


def execute(selected, suite, output_dir, *, context=None, worker=None):
    if worker is None:
        from .runner import run as worker
    output = Path(output_dir).expanduser().resolve()
    if output.with_name(output.name + ".tar.gz").exists():
        raise ValueError("archive already exists; choose a fresh output directory")
    output.mkdir(parents=True, exist_ok=False)
    manifest = campaign_plan(selected, suite)
    manifest.update(
        executed=True, started_at=utc_now(), phase="running", context=context or {}
    )
    manifest["errors"] = []
    manifest_path = output / "campaign.json"
    write_json(manifest_path, manifest)
    baseline = None
    try:
        write_json(output / "environment.json", environment_info())
        manifest["inventory_before"] = capture_inventory(output, "inventory-before")
        write_json(manifest_path, manifest)
        for stage, (name, config) in zip(manifest["stages"], selected):
            directory = output / name
            directory.mkdir()
            config = replace(config, artifact_dir=str(directory / "evidence"))
            stage.update(status="RUNNING", started_at=utc_now(), config=asdict(config))
            write_json(manifest_path, manifest)
            started = time.monotonic()
            report = worker(config)
            path = directory / "report.json"
            status, reasons = assess(report, config, baseline)
            # Set observed failure before optional filesystem operations can fail.
            manifest["status"] = status if status != "PASS" else "INCONCLUSIVE"
            stage.update(
                status=status,
                reasons=reasons,
                elapsed_seconds=round(time.monotonic() - started, 3),
                report=path.relative_to(output).as_posix(),
                finished_at=utc_now(),
            )
            write_json(path, report)
            write_json(manifest_path, manifest)
            stage["sha256"] = fingerprint(path)
            if isinstance(report, dict) and isinstance(report.get("identity"), dict):
                stage["identity"] = report["identity"]
                if baseline is None:
                    baseline = identity_key(report["identity"])
                    manifest["identity_continuity"] = (
                        "UUID" if baseline.get("uuid") else "RUNTIME_ONLY"
                    )
            if config.power_target_w is not None:
                manifest["power_validation"] = (
                    "PASS" if status == "PASS" else "INCONCLUSIVE"
                )
            write_json(manifest_path, manifest)
            print(f"{name}: {status}", file=sys.stderr, flush=True)
            if status != "PASS":
                break
        manifest["complete"] = all(
            stage["status"] == "PASS" for stage in manifest["stages"]
        )
        if manifest["complete"]:
            manifest["status"] = "PASS"
    except (Exception, KeyboardInterrupt) as exc:
        manifest["errors"].append(
            {"reason": type(exc).__name__, "detail": str(exc)[:1000]}
        )
        if manifest["status"] != "FAIL":
            manifest["status"] = "INCONCLUSIVE"
        for stage in manifest["stages"]:
            if stage["status"] == "RUNNING":
                stage.update(
                    status="INCONCLUSIVE",
                    reasons=["campaign_interrupted"],
                    finished_at=utc_now(),
                )
    manifest.update(phase="finished", finished_at=utc_now())
    try:
        manifest["inventory_after"] = capture_inventory(output, "inventory-after")
        write_json(manifest_path, manifest)
        seal(output)
    except OSError as exc:
        manifest["errors"].append(
            {"reason": "evidence_bundle_failed", "detail": str(exc)[:1000]}
        )
        if manifest["status"] != "FAIL":
            manifest["status"] = "INCONCLUSIVE"
        try:
            write_json(manifest_path, manifest)
        except OSError:
            pass  # The CLI still returns observed FAIL and the storage error as JSON.
    return manifest


@contextmanager
def termination_handler():
    """Let the worker's finally block reap its process group on scheduler SIGTERM."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def interrupt(_signum, _frame):
        raise KeyboardInterrupt("SIGTERM")

    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def run(argv):
    parser = argparse.ArgumentParser(
        prog="omnismi self-test campaign",
        description="Run a staged acceptance campaign on one existing device. "
        "No provisioning, upload or cloud shutdown; "
        "PASS is not hardware certification.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--plan",
        action="store_true",
        help="Offline plan; no runtime imports or file writes.",
    )
    mode.add_argument(
        "--run",
        action="store_true",
        help="Execute bounded tests and save an evidence bundle.",
    )
    parser.add_argument(
        "--target",
        required=True,
        choices=[t["id"] for t in target_catalog()["targets"]],
    )
    parser.add_argument("--suite", choices=("pilot", "acceptance"), default="pilot")
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--memory-mib", type=int, default=256)
    parser.add_argument("--stage-timeout", type=float, default=900)
    parser.add_argument("--duration", type=float, default=300)
    parser.add_argument("--power-target-w", type=float)
    parser.add_argument(
        "--output-dir", help="Required for --run. Must not already exist."
    )
    parser.add_argument(
        "--provider", choices=("local", "runpod", "gcp", "other"), default="local"
    )
    parser.add_argument(
        "--instance-label",
        help="User-supplied deployment identifier, not proof of a physical device.",
    )
    parser.add_argument(
        "--image-ref",
        help="Optional image digest or runtime image identifier for provenance.",
    )
    args = parser.parse_args(argv)
    try:
        selected = stages(
            args.target,
            args.suite,
            device=args.device,
            seed=args.seed,
            memory_mib=args.memory_mib,
            stage_timeout=args.stage_timeout,
            duration=args.duration,
            power_target_w=args.power_target_w,
        )
        if args.plan:
            report = campaign_plan(selected, args.suite)
        else:
            if not args.output_dir:
                raise ValueError("--run requires --output-dir")
            with termination_handler():
                report = execute(
                    selected,
                    args.suite,
                    args.output_dir,
                    context={
                        "provider": args.provider,
                        "instance_label": args.instance_label,
                        "image_ref": args.image_ref,
                    },
                )
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "INCONCLUSIVE", "error": str(exc)}))
        return 64
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if args.plan else EXIT_CODES[report["status"]]
