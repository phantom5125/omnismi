"""JSON-first hardware self-test command; planning needs no optional dependency."""

from __future__ import annotations

import argparse
import json

from .catalog import OPERATORS, VENDORS, Config, plan
from .targets import target_catalog, target_profile


def run(argv):
    if argv and argv[0] == "campaign":
        from .acceptance import run as run_campaign

        return run_campaign(argv[1:])
    parser = argparse.ArgumentParser(
        prog="omnismi self-test",
        description="Compare accelerator operators against CPU references. "
        "PASS is not a whole-device health certificate.",
        epilog="For multi-stage acceptance: omnismi self-test campaign --help",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--plan",
        action="store_true",
        help="Print coverage without importing a compute runtime.",
    )
    mode.add_argument(
        "--run",
        action="store_true",
        help="Execute workloads on the selected accelerator.",
    )
    parser.add_argument("--vendor", choices=VENDORS)
    parser.add_argument(
        "--target",
        choices=[item["id"] for item in target_catalog()["targets"]],
        help="Reviewed model preset; verifies runtime model before execution.",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=0,
        help="Framework runtime index, not the global omnismi index.",
    )
    parser.add_argument(
        "--profile", choices=("smoke", "extended", "soak"), default="smoke"
    )
    parser.add_argument("--seed", type=int, default=20260930)
    parser.add_argument("--passes", type=int, default=1)
    parser.add_argument("--memory-mib", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument(
        "--duration",
        type=float,
        default=60,
        help="Soak phase seconds, within the total timeout.",
    )
    parser.add_argument(
        "--operators",
        default=",".join(OPERATORS),
        help="Comma-separated operator selection.",
    )
    parser.add_argument("--power-target-w", type=float)
    parser.add_argument("--require-unit-coverage", action="store_true")
    parser.add_argument(
        "--artifact-dir",
        help="Store full inputs/outputs of the first numerical failure as NPZ.",
    )
    args = vars(parser.parse_args(argv))
    planning = args.pop("plan")
    args.pop("run")
    args["operators"] = tuple(args["operators"].split(","))
    try:
        if args["target"] and args["vendor"] is None:
            args["vendor"] = target_profile(args["target"])["vendor"]
        if args["vendor"] is None:
            raise ValueError("provide --vendor or --target")
        config = Config(**args)
        config.validate()
        if planning:
            report = plan(config)
        else:
            from .runner import run as run_worker

            report = run_worker(config)
    except (ValueError, OSError) as exc:
        print(json.dumps({"status": "INCONCLUSIVE", "error": str(exc)}))
        return 64
    print(json.dumps(report, indent=2, allow_nan=False))
    return (
        0 if planning else {"PASS": 0, "FAIL": 2, "INCONCLUSIVE": 3}[report["status"]]
    )
