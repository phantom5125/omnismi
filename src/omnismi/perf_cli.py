"""Offline comparison, baseline authoring and explicitly requested live probes."""

from __future__ import annotations

import argparse
import json
import stat
import sys
from pathlib import Path
from typing import Any

from omnismi.baselines import build_baseline
from omnismi.performance import (
    SIGNATURE_FIELDS,
    evaluate_performance,
    measurement_from_bench,
)
from omnismi.probe_runtime import run_probe


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _read_json(path: str) -> dict[str, Any]:
    source = Path(path)
    if not stat.S_ISREG(source.stat().st_mode):
        raise ValueError("Expected a regular JSON file")
    with source.open("rb") as stream:
        raw = stream.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError("Performance input exceeds 1 MiB")

    def reject_constant(value: str) -> None:
        raise ValueError(f"Nonfinite JSON constant: {value}")

    value = json.loads(raw, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def run(argv: list[str]) -> int:
    parser = _Parser(prog="omnismi perf-doctor")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--input", help="Versioned measurement or BenchReport JSON.")
    mode.add_argument(
        "--run",
        choices=["bandwidth", "compute"],
        help="Explicitly execute a bounded accelerator workload.",
    )
    mode.add_argument(
        "--build-baseline",
        metavar="ID",
        help="Build a sustained baseline from distinct runs.",
    )
    parser.add_argument(
        "--measurement",
        action="append",
        default=[],
        help="Measurement file; repeat for baseline construction.",
    )
    parser.add_argument("--policy", help="Baseline thresholds and rationale JSON.")
    parser.add_argument(
        "--theoretical-peak", help="Optional documented theoretical reference JSON."
    )
    parser.add_argument("--baseline", help="Explicit, provenance-backed baseline JSON.")
    parser.add_argument("--context", help="Missing measurement conditions as JSON.")
    parser.add_argument("--result-id", help="Select one result in a BenchReport.")
    parser.add_argument("--vendor", choices=["nvidia", "amd", "alibaba", "cambricon"])
    parser.add_argument(
        "--device", type=int, default=0, help="Runtime-local device index for --run."
    )
    parser.add_argument(
        "--memory-mib", type=int, default=64, help="Total tensor allocation budget."
    )
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--pattern", choices=["copy", "triad"], default="copy")
    parser.add_argument(
        "--save-measurement",
        help="Create a new measurement file from --run, without overwriting.",
    )
    try:
        args = parser.parse_args(argv)
        if args.build_baseline:
            if (
                args.context
                or args.result_id
                or args.baseline
                or args.save_measurement
                or args.vendor
            ):
                raise ValueError(
                    "Baseline creation requires measurement and reference metadata"
                )
            baseline = build_baseline(
                [_read_json(path) for path in args.measurement],
                baseline_id=args.build_baseline,
                policy=_read_json(args.policy) if args.policy else None,
                theoretical_peak=(
                    _read_json(args.theoretical_peak) if args.theoretical_peak else None
                ),
            )
            print(json.dumps(baseline, separators=(",", ":"), allow_nan=False))
            return 0
        if args.measurement or args.policy or args.theoretical_peak:
            raise ValueError(
                "Measurement lists and reference metadata require --build-baseline"
            )
        probe = None
        if args.run:
            if not args.vendor or args.result_id:
                raise ValueError(
                    "--run requires --vendor and does not accept --result-id"
                )
            context = _read_json(args.context) if args.context else {}
            if set(context) - set(SIGNATURE_FIELDS):
                raise ValueError("Unknown context fields")
            if args.save_measurement and Path(args.save_measurement).exists():
                raise ValueError("Measurement output already exists")
            probe = run_probe(
                mode=args.run,
                vendor=args.vendor,
                device=args.device,
                memory_mib=args.memory_mib,
                repeats=args.repeats,
                timeout=args.timeout,
                pattern=args.pattern,
            )
            measurement = probe["data"].get("measurement")
            if measurement is None:
                print(json.dumps(probe, separators=(",", ":"), allow_nan=False))
                return {"PASS": 0, "WARN": 1, "FAIL": 2, "INCONCLUSIVE": 3}[
                    probe["status"]
                ]
            for key, value in context.items():
                if (
                    measurement["signature"].get(key) is not None
                    and measurement["signature"][key] != value
                ):
                    raise ValueError(f"Context cannot override recorded {key}")
                measurement["signature"][key] = value
            measurement["probe_evidence"] = {
                key: value
                for key, value in probe["data"].items()
                if key != "measurement"
            }
            if args.save_measurement:
                serialized = json.dumps(measurement, allow_nan=False, indent=2) + "\n"
                with Path(args.save_measurement).open("x") as stream:
                    stream.write(serialized)
        else:
            if args.save_measurement or args.vendor:
                raise ValueError("--save-measurement and --vendor require --run")
            measurement = _read_json(args.input)
            if measurement.get("kind") == "BenchReport":
                measurement = measurement_from_bench(
                    measurement,
                    context=_read_json(args.context) if args.context else None,
                    result_id=args.result_id,
                )
            elif args.context or args.result_id:
                raise ValueError(
                    "--context and --result-id apply only to BenchReport or live input"
                )
        report = evaluate_performance(
            measurement, _read_json(args.baseline) if args.baseline else None
        )
        if probe is not None:
            report["data"]["measurement"] = measurement
            report["scope"]["input_kind"] = "explicit_live_probe"
            report["scope"]["probe"] = probe["scope"]
        print(json.dumps(report, separators=(",", ":"), allow_nan=False))
        return {"PASS": 0, "WARN": 1, "FAIL": 2, "INCONCLUSIVE": 3}[report["status"]]
    except (ValueError, OSError) as exc:
        print(f"omnismi perf-doctor: {exc}", file=sys.stderr)
        return 64
