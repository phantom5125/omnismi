"""Explicit SDK-local compilation; importing Omnismi never invokes a compiler."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from importlib.resources import files
from pathlib import Path


def build_probe(*, include_dir: str, library_dir: str, output: str) -> dict[str, str]:
    if sys.platform != "linux":
        raise ValueError("The CNDEV SDK collector build requires Linux")
    include, library, destination = (
        Path(x).resolve() for x in (include_dir, library_dir, output)
    )
    header = include / "cndev.h"
    if not header.is_file() or not library.is_dir():
        raise ValueError(
            "Provide the installed SDK header directory and library directory"
        )
    if destination.exists() or not destination.parent.is_dir():
        raise ValueError("Output must be a new file in an existing directory")
    compiler = shutil.which("cc")
    if compiler is None:
        raise ValueError("A C compiler is required")
    source = files("omnismi.backends").joinpath("cndev_probe.c").read_bytes()
    with tempfile.TemporaryDirectory(prefix="omnismi-cndev-") as temporary:
        root = Path(temporary)
        (root / "probe.c").write_bytes(source)
        args = [
            compiler,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror=implicit-function-declaration",
            f"-I{include}",
            str(root / "probe.c"),
            f"-L{library}",
            "-lcndev",
            f"-Wl,-rpath,{library}",
            "-o",
            str(root / "probe"),
        ]
        completed = subprocess.run(args, capture_output=True, timeout=60, check=False)
        if completed.returncode:
            raise ValueError(
                "CNDEV compile/link failed: "
                + completed.stderr[-4096:].decode(errors="replace")
            )
        # Reserve the output atomically; do not replace an existing program.
        with destination.open("xb") as stream:
            stream.write((root / "probe").read_bytes())
        destination.chmod(0o755)
    return {
        "executable": str(destination),
        "header_sha256": hashlib.sha256(header.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "sdk_api": "CNDEV_VERSION_6",
    }


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="omnismi cndev-build")
    parser.add_argument("--include-dir", required=True)
    parser.add_argument("--library-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        result = build_probe(
            include_dir=args.include_dir,
            library_dir=args.library_dir,
            output=args.output,
        )
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"omnismi cndev-build: {exc}", file=sys.stderr)
        return 64


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
