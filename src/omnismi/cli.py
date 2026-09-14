"""Agent-friendly Omnismi CLI with stable JSON on stdout."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from omnismi import __version__
from omnismi.api import gpus
from omnismi.preflight import build_inventory, build_preflight, device_snapshot
from omnismi.visibility import filter_gpus_by_visibility


def _gib_to_bytes(gib: float) -> int:
    return int(gib * (1024**3))


def _emit_json(payload: dict, *, human: bool) -> None:
    text = json.dumps(payload, indent=2, sort_keys=False, default=str)
    sys.stdout.write(text)
    if not text.endswith("\n"):
        sys.stdout.write("\n")
    if human:
        summary = payload.get("summary") or {}
        sys.stderr.write(
            f"omnismi {payload.get('command', '?')}: "
            f"ok={payload.get('ok')} exit={payload.get('exit_code')} "
            f"gpus={summary.get('gpu_count', len(payload.get('devices') or []))} "
            f"vendors={summary.get('vendors', [])}\n"
        )


def _cmd_preflight(args: argparse.Namespace) -> int:
    min_free = args.min_free_bytes
    if args.min_free_gib is not None:
        converted = _gib_to_bytes(args.min_free_gib)
        min_free = converted if min_free is None else max(min_free, converted)

    payload = build_preflight(
        min_gpus=args.min_gpus,
        min_free_bytes=min_free,
        require_idle=args.require_idle,
        visible_only=args.visible_only,
        include_topology=args.topology,
    )
    _emit_json(payload, human=args.human)
    return int(payload.get("exit_code", 1))


def _cmd_inventory(args: argparse.Namespace) -> int:
    payload = build_inventory(visible_only=args.visible_only)
    _emit_json(payload, human=args.human)
    return int(payload.get("exit_code", 1))


def _cmd_metrics(args: argparse.Namespace) -> int:
    try:
        devices = list(gpus())
        selected, visibility = filter_gpus_by_visibility(
            devices, visible_only=args.visible_only
        )
        rows = []
        for logical_index, device in enumerate(selected):
            rows.append(
                device_snapshot(device, logical_index=logical_index, realtime=True)
            )
        exit_code = 0 if rows else 2
        payload = {
            "schema_version": 1,
            "command": "metrics",
            "ok": exit_code == 0,
            "exit_code": exit_code,
            "visibility": {
                "mode": visibility.mode,
                "env": visibility.env,
                "physical_indices": visibility.physical_indices,
                "logical_indices": visibility.logical_indices,
            },
            "devices": rows,
            "warnings": [],
            "failures": []
            if rows
            else [{"code": "no_accelerators", "message": "no visible accelerators"}],
            "metrics_mode": "snapshot_realtime",
        }
    except Exception as exc:
        payload = {
            "schema_version": 1,
            "command": "metrics",
            "ok": False,
            "exit_code": 10,
            "error": str(exc),
            "devices": [],
            "warnings": [],
            "failures": [{"code": "backend_error", "message": str(exc)}],
        }
    _emit_json(payload, human=args.human)
    return int(payload.get("exit_code", 1))


def _cmd_version(_: argparse.Namespace) -> int:
    sys.stdout.write(f"{__version__}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omnismi",
        description=(
            "Cross-vendor accelerator observability for AI agents and Python apps. "
            "JSON is written to stdout; use --human for a short stderr summary."
        ),
    )
    parser.add_argument("--version", action="version", version=f"omnismi {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--json",
            action="store_true",
            default=True,
            help="emit JSON on stdout (default; kept for agent flag compatibility)",
        )
        p.add_argument(
            "--human",
            action="store_true",
            help="also print a one-line human summary to stderr",
        )
        vis = p.add_mutually_exclusive_group()
        vis.add_argument(
            "--visible-only",
            dest="visible_only",
            action="store_true",
            default=True,
            help="honor CUDA_VISIBLE_DEVICES (default)",
        )
        vis.add_argument(
            "--all-devices",
            dest="visible_only",
            action="store_false",
            help="ignore CUDA_VISIBLE_DEVICES and list all discovered devices",
        )

    pre = sub.add_parser(
        "preflight",
        help="one-shot inventory + metrics gate for agents (stable JSON)",
    )
    add_common(pre)
    pre.add_argument("--min-gpus", type=int, default=0, help="require at least N GPUs")
    pre.add_argument(
        "--min-free-bytes",
        type=int,
        default=None,
        help="require each GPU to have at least this many free bytes",
    )
    pre.add_argument(
        "--min-free-gib",
        type=float,
        default=None,
        help="same as --min-free-bytes, in GiB",
    )
    pre.add_argument(
        "--require-idle",
        action="store_true",
        help="require no compute processes (not enforced until processes API lands)",
    )
    pre.add_argument(
        "--topology",
        action="store_true",
        help="request topology (omitted with warning until topology API lands)",
    )
    pre.set_defaults(func=_cmd_preflight)

    inv = sub.add_parser("inventory", help="list accelerators as JSON")
    add_common(inv)
    inv.set_defaults(func=_cmd_inventory)

    met = sub.add_parser("metrics", help="snapshot metrics as JSON")
    add_common(met)
    met.set_defaults(func=_cmd_metrics)

    ver = sub.add_parser("version", help="print package version")
    ver.set_defaults(func=_cmd_version)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return int(code) if isinstance(code, int) else 1
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
