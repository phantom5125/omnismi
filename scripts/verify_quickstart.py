"""Execute the documented offline quickstart commands against an installed wheel."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import omnismi

ROOT = Path(__file__).resolve().parents[1]
BLOCK = re.compile(
    r"<!-- quickstart-smoke: ([a-z]+) -->\s*```bash\n(.*?)\n```", re.DOTALL
)
CASES = {
    "help": (0, None),
    "decode": (2, "FAIL"),
    "log": (2, "FAIL"),
    "unknown": (3, "INCONCLUSIVE"),
    "performance": (1, "WARN"),
}
DOCUMENTS = {
    "README.md": {"decode"},
    "docs/quickstart.md": set(CASES),
    "docs/quickstart.zh-CN.md": set(CASES),
}


def main() -> None:
    assert "site-packages" in omnismi.__file__, "Install the wheel first"
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    commands = 0
    for document, expected_cases in DOCUMENTS.items():
        blocks = BLOCK.findall((ROOT / document).read_text(encoding="utf-8"))
        assert len(blocks) == len(expected_cases)
        assert {case for case, _ in blocks} == expected_cases, document
        for case, command in blocks:
            # Deliberately no shell: only the visible one-line offline CLI command.
            assert "\n" not in command, (document, case)
            argv = shlex.split(command)
            assert argv[:3] == ["python", "-m", "omnismi"], (document, case)
            assert argv[3] in {"decode", "diagnose", "perf-doctor"}
            flags = {argument.split("=", 1)[0] for argument in argv}
            assert not {"--run", "--collect", "--self-test"}.intersection(flags)
            result = subprocess.run(
                [sys.executable, *argv[1:]],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                timeout=10,
            )
            code, status = CASES[case]
            assert result.returncode == code, (document, case, result.stderr)
            if status is None:
                assert "--namespace" in result.stdout
            else:
                report = json.loads(result.stdout)
                assert report["schema_version"] == 1
                assert report["status"] == status, (document, case)
                if case == "performance":
                    assert report["data"]["percent_of_expected_sustained"] == 80
                    assert report["data"]["percent_of_theoretical_peak"] == 40
                else:
                    assert report["scope"]["current_hardware_health"] == "INCONCLUSIVE"
                    if case != "unknown":
                        assert report["data"]["findings"] and report["sources"]
            commands += 1
    # Exercise the wheel's console entry point as well as python -m omnismi.
    console = Path(sys.executable).with_name("omnismi")
    subprocess.run(
        [str(console), "--help"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    print(
        f"Quickstart: {commands} documented offline commands and console entry passed"
    )


if __name__ == "__main__":
    main()
