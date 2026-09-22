"""Offline performance CLI; deliberately does not schedule a GPU workload."""

from __future__ import annotations

import argparse
import json
import stat
import sys
from pathlib import Path
from typing import Any

from omnismi.performance import evaluate_performance, measurement_from_bench


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
    parser.add_argument("--input", required=True, help="Versioned measurement JSON.")
    parser.add_argument("--baseline", help="Explicit, provenance-backed baseline JSON.")
    parser.add_argument(
        "--context", help="Missing BenchReport signature fields as JSON."
    )
    parser.add_argument("--result-id", help="Select one result in a BenchReport.")
    try:
        args = parser.parse_args(argv)
        measurement = _read_json(args.input)
        if measurement.get("kind") == "BenchReport":
            measurement = measurement_from_bench(
                measurement,
                context=_read_json(args.context) if args.context else None,
                result_id=args.result_id,
            )
        elif args.context or args.result_id:
            raise ValueError(
                "--context and --result-id apply only to BenchReport input"
            )
        report = evaluate_performance(
            measurement, _read_json(args.baseline) if args.baseline else None
        )
        print(json.dumps(report, separators=(",", ":"), allow_nan=False))
        return {"PASS": 0, "WARN": 1, "FAIL": 2, "INCONCLUSIVE": 3}[report["status"]]
    except (ValueError, OSError) as exc:
        print(f"omnismi perf-doctor: {exc}", file=sys.stderr)
        return 64
