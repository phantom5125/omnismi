"""Compile the optional SAIL workload on a Linux host with its installed SDK."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from importlib.resources import files
from pathlib import Path

from omnismi.backends.command import query_text
from omnismi.errors import BackendError

SOURCES = ("sail_probe.hg", "sail_probe_host.hpp")


def build_probe(
    *,
    output: str,
    compiler: str = "hgcc",
    architectures: tuple[str, ...] = ("ppu_10", "ppu_15"),
    timeout: float = 120,
) -> dict:
    if sys.platform != "linux":
        raise ValueError("The SAIL probe build requires a Linux SAIL SDK host")
    if not architectures or set(architectures) - {"ppu_10", "ppu_15"}:
        raise ValueError("Supported targets are ppu_10 and ppu_15")
    destination = Path(output).absolute()
    if (
        destination.exists()
        or destination.is_symlink()
        or not destination.parent.is_dir()
    ):
        raise ValueError("Output must be a new file in an existing directory")
    executable = shutil.which(compiler)
    if executable is None:
        raise ValueError("Install the SAIL SDK and provide its hgcc compiler")
    sources = {
        name: files("omnismi.backends").joinpath(name).read_bytes() for name in SOURCES
    }
    with tempfile.TemporaryDirectory(prefix="omnismi-sail-") as temporary:
        root = Path(temporary)
        for name, data in sources.items():
            (root / name).write_bytes(data)
        args = [executable, "-std=c++17", "-O3"]
        args.extend(
            f"--gpu-architecture={arch}" for arch in dict.fromkeys(architectures)
        )
        args.extend([str(root / "sail_probe.hg"), "-o", str(root / "probe")])
        query_text(args, timeout=timeout)
        with destination.open("xb") as stream:
            stream.write((root / "probe").read_bytes())
        destination.chmod(0o755)
    return {
        "executable": str(destination),
        "compiler": executable,
        "architectures": list(dict.fromkeys(architectures)),
        "source_sha256": {
            name: hashlib.sha256(data).hexdigest() for name, data in sources.items()
        },
        "probe_version": "hggc-tiled16-v1",
    }


def run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="omnismi sail-build")
    parser.add_argument("--output", required=True)
    parser.add_argument("--compiler", default="hgcc")
    parser.add_argument("--architecture", choices=["ppu_10", "ppu_15"], action="append")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args(argv)
    try:
        result = build_probe(
            output=args.output,
            compiler=args.compiler,
            architectures=tuple(args.architecture or ("ppu_10", "ppu_15")),
            timeout=args.timeout,
        )
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, BackendError) as exc:
        print(f"omnismi sail-build: {exc}", file=sys.stderr)
        return 64
