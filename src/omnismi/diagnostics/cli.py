"""JSON-only diagnostic commands, isolated from the legacy CLI dispatch."""

from __future__ import annotations

import argparse
import json
import stat
import sys
from pathlib import Path

from omnismi.diagnostics.collectors import collect_kernel_log
from omnismi.diagnostics.engine import decode_error, diagnose
from omnismi.diagnostics.hardware import collect_hardware
from omnismi.diagnostics.parsers import MAX_BYTES
from omnismi.probe_runtime import run_probe

EXIT_CODES = {"PASS": 0, "WARN": 1, "FAIL": 2, "INCONCLUSIVE": 3}


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def run(argv: list[str]) -> int:
    """Run one command. Existing overview/doctor/bench exit codes are unchanged."""
    parser = _Parser(prog=f"omnismi {argv[0]}")
    parser.add_argument("--driver-version")
    parser.add_argument("--model")
    if argv[0] == "decode":
        parser.add_argument("--vendor", required=True)
        parser.add_argument("--namespace", required=True)
        parser.add_argument("--code", required=True)
    else:
        inputs = parser.add_mutually_exclusive_group(required=True)
        inputs.add_argument("--input", help="UTF-8 regular file, or - for stdin.")
        inputs.add_argument("--collect", choices=["passive", "hardware"])
        inputs.add_argument(
            "--self-test",
            action="store_true",
            help="Explicit bounded memory and compute correctness test.",
        )
        parser.add_argument(
            "--vendor", choices=["nvidia", "amd", "alibaba", "cambricon"]
        )
        parser.add_argument(
            "--device", type=int, default=0, help="Runtime-local index for --self-test."
        )
        parser.add_argument("--memory-mib", type=int, default=64)
        parser.add_argument(
            "--format", choices=["dmesg", "ras", "events"], default="dmesg"
        )
        parser.add_argument("--block")
        parser.add_argument("--pci-address")
        parser.add_argument("--include-raw", action="store_true")
        parser.add_argument("--max-events", type=int, default=500)
        parser.add_argument("--timeout", type=float)
    try:
        args = parser.parse_args(argv[1:])
        context = {
            key: value
            for key, value in {
                "driver_version": args.driver_version,
                "model": args.model,
            }.items()
            if value is not None
        }
        if argv[0] == "decode":
            report = decode_error(
                args.vendor, args.namespace, args.code, context=context
            )
        elif args.self_test:
            if not args.vendor:
                raise ValueError("--self-test requires --vendor")
            report = run_probe(
                mode="self-test",
                vendor=args.vendor,
                device=args.device,
                memory_mib=args.memory_mib,
                timeout=args.timeout if args.timeout is not None else 30,
            )
        elif args.collect == "hardware":
            if args.format != "dmesg" or args.block or args.pci_address:
                raise ValueError(
                    "Hardware collection cannot use supplied log format/identity"
                )
            report = collect_hardware(
                vendor=args.vendor,
                timeout=args.timeout if args.timeout is not None else 30,
            )
        else:
            if args.vendor:
                raise ValueError(
                    "--vendor applies to --self-test; log parsing identifies vendors"
                )
            collected = None
            input_truncated = False
            if args.collect:
                if args.format != "dmesg" or args.block or args.pci_address:
                    raise ValueError("Passive collection supports only dmesg format")
                collected = collect_kernel_log(
                    timeout=args.timeout if args.timeout is not None else 5
                )
                text = collected.pop("text")
            elif args.input == "-":
                text = sys.stdin.read(MAX_BYTES + 1)
            else:
                path = Path(args.input)
                if not stat.S_ISREG(path.stat().st_mode):
                    raise ValueError("Input must be a regular file; use - for stdin")
                with path.open("rb") as stream:
                    raw = stream.read(MAX_BYTES + 1)
                input_truncated = len(raw) > MAX_BYTES
                if input_truncated:
                    raw = raw[:MAX_BYTES]
                    raw = raw.rsplit(b"\n", 1)[0] if b"\n" in raw else b""
                text = raw.decode("utf-8", errors="strict")
            report = diagnose(
                text,
                input_format=args.format,
                block=args.block,
                pci_address=args.pci_address,
                context=context,
                include_raw=args.include_raw,
                max_events=args.max_events,
            )
            if input_truncated:
                report["limitations"].append("input_bytes_truncated")
            if collected is not None:
                report["scope"]["input_kind"] = "passive_kernel_log_collection"
                report["data"]["collection"] = collected
                if collected["status"] != "ok":
                    report["limitations"].append(
                        f"Collection incomplete: {collected['reason']}"
                    )
        print(json.dumps(report, separators=(",", ":"), allow_nan=False))
        return EXIT_CODES[report["status"]]
    except (ValueError, OSError) as exc:
        print(f"omnismi {argv[0]}: {exc}", file=sys.stderr)
        return 64
