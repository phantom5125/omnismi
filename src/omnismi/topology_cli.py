"""Topology JSON command and optional read-only affinity recommendation."""

from __future__ import annotations

import argparse
import json
import stat
import sys
from pathlib import Path

from omnismi.topology import (
    discover_topology,
    parse_nvidia_matrix,
    recommend_affinity,
)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _read(path: str) -> str:
    source = Path(path)
    if not stat.S_ISREG(source.stat().st_mode):
        raise ValueError("Expected a regular input file")
    with source.open("rb") as stream:
        raw = stream.read(1_048_577)
    if len(raw) > 1_048_576:
        raise ValueError("Input exceeds 1 MiB")
    return raw.decode("utf-8")


def run(argv: list[str]) -> int:
    parser = _Parser(prog="omnismi topology")
    parser.add_argument("--input", help="Replay a saved topology JSON report.")
    parser.add_argument(
        "--nvidia-matrix", help="Import a saved nvidia-smi topo -m matrix."
    )
    parser.add_argument("--recommend-affinity", action="store_true")
    parser.add_argument("--device", help="Stable PCI node ID, e.g. pci:0000:41:00.0.")
    try:
        args = parser.parse_args(argv)
        if bool(args.device) != args.recommend_affinity:
            raise ValueError("Use --recommend-affinity and --device together")
        report = json.loads(_read(args.input)) if args.input else discover_topology()
        if (
            not isinstance(report, dict)
            or report.get("report_type") != "topology"
            or report.get("schema_version") != 1
            or report.get("status") not in {"PASS", "WARN", "INCONCLUSIVE"}
            or not isinstance(report.get("data"), dict)
        ):
            raise ValueError("Expected a version 1 topology report")
        if args.nvidia_matrix:
            report["data"]["nvidia_matrix"] = parse_nvidia_matrix(
                _read(args.nvidia_matrix)
            )
        if args.recommend_affinity:
            recommendation = recommend_affinity(report, args.device)
            report["data"]["affinity_recommendation"] = recommendation
            if recommendation["status"] != "PASS":
                report["status"] = recommendation["status"]
        print(json.dumps(report, separators=(",", ":"), allow_nan=False))
        return {"PASS": 0, "WARN": 1, "INCONCLUSIVE": 3}[report["status"]]
    except (OSError, ValueError) as exc:
        print(f"omnismi topology: {exc}", file=sys.stderr)
        return 64
