"""Private subprocess entry point with atomic checkpoints."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .catalog import Config, plan


def main():
    config = Config(**json.loads(sys.argv[1]))
    destination = Path(sys.argv[2])

    def checkpoint(report):
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, allow_nan=False), encoding="utf-8")
        temporary.replace(destination)

    checkpoint(plan(config))
    try:
        from .engine import execute

        execute(config, checkpoint)
    except Exception as exc:
        # Preserve any already-observed failure even if later cleanup/imports fail.
        report = json.loads(destination.read_text(encoding="utf-8"))
        report.update(complete=False, executed=True)
        if report["status"] != "FAIL":
            report["status"] = "INCONCLUSIVE"
        report.setdefault("errors", []).append(
            {"reason": "worker_error", "detail": str(exc)[:1000]}
        )
        checkpoint(report)


if __name__ == "__main__":
    main()
