"""Dependency-free, reproducible operator coverage plans."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

VENDORS = ("nvidia", "amd", "cambricon", "alibaba", "google")
OPERATORS = ("copy", "add", "mul", "sum", "gather", "sort", "topk", "matmul")


@dataclass(frozen=True)
class Config:
    vendor: str
    device: int = 0
    profile: str = "smoke"
    seed: int = 20260930
    passes: int = 1
    memory_mib: int = 256
    timeout: float = 120
    duration: float = 60
    operators: tuple[str, ...] = OPERATORS
    require_unit_coverage: bool = False
    power_target_w: float | None = None
    artifact_dir: str | None = None
    target: str | None = None

    def validate(self):
        if self.target:
            from .targets import target_profile

            if target_profile(self.target)["vendor"] != self.vendor:
                raise ValueError("target and vendor do not match")
        if self.vendor not in VENDORS or self.profile not in (
            "smoke",
            "extended",
            "soak",
        ):
            raise ValueError("unsupported vendor or profile")
        for name, value, low, high in (
            ("device", self.device, 0, 4095),
            ("seed", self.seed, 0, 2**32 - 1),
            ("passes", self.passes, 1, 100),
            ("memory_mib", self.memory_mib, 16, 4096),
        ):
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} must be an integer in [{low}, {high}]")
        for name, value, high in (
            ("timeout", self.timeout, 3600),
            ("duration", self.duration, 1800),
        ):
            if not math.isfinite(value) or not 0 < value <= high:
                raise ValueError(f"{name} must be finite and in (0, {high}]")
        if not self.operators or set(self.operators) - set(OPERATORS):
            raise ValueError("select at least one supported operator")
        if len(set(self.operators)) != len(self.operators):
            raise ValueError("duplicate operators")
        if self.power_target_w is not None:
            if not math.isfinite(self.power_target_w) or self.power_target_w <= 0:
                raise ValueError("power_target_w must be finite and positive")
            if self.profile != "soak":
                raise ValueError("power_target_w requires the soak profile")
        if self.profile == "soak" and "matmul" not in self.operators:
            raise ValueError("soak requires matmul in operators")


@dataclass(frozen=True)
class Case:
    id: str
    operator: str
    shape: tuple[int, int]
    dtype: str = "float32"
    pattern: str = "random"
    layout: str = "contiguous"
    k: int = 1
    largest: bool = True
    sorted: bool = True

    @property
    def estimated_device_bytes(self):
        # Conservative live tensor estimate, NOT a bound on framework workspaces.
        return math.prod(self.shape) * 64


def cases(config: Config) -> list[Case]:
    config.validate()
    result = []

    def add(op, shape, **kwargs):
        if config.vendor == "google":
            # XLA owns physical layouts; only logical arrays are portable.
            kwargs["layout"] = "contiguous"
        result.append(Case(f"{len(result):04d}-{op}", op, shape, **kwargs))

    for op in OPERATORS:
        if op not in config.operators or op == "topk":
            continue
        add(op, (64, 64) if op == "matmul" else (7, 257))
    # Boundary k, odd widths, ties, both directions, actual strided inputs.
    for width, k, largest, sorted_, pattern, layout in (
        (257, 1, True, True, "random", "contiguous"),
        (257, 7, True, False, "ties", "contiguous"),
        (257, 256, False, True, "random", "strided"),
        (257, 257, False, False, "ties", "strided"),
        (1024, 33, True, True, "near_ties", "contiguous"),
        (1025, 32, False, True, "alternating", "contiguous"),
    ):
        if "topk" in config.operators:
            add(
                "topk",
                (7, width),
                k=k,
                largest=largest,
                sorted=sorted_,
                pattern=pattern,
                layout=layout,
            )
    if config.profile in ("extended", "soak"):
        dtypes = ("float32", "float16", "bfloat16", "int32")
        if config.target:
            from .targets import target_profile

            dtypes = target_profile(config.target)["dtypes"]
        for dtype in dtypes:
            for op in config.operators:
                if op == "topk":
                    for width in (31, 32, 33, 1023, 1024, 1025, 4097):
                        for i, k in enumerate(
                            sorted({1, min(32, width), width // 2, width})
                        ):
                            for largest in (False, True):
                                add(
                                    op,
                                    (17, width),
                                    dtype=dtype,
                                    k=k,
                                    largest=largest,
                                    sorted=bool(i % 2),
                                    pattern=(
                                        "ties",
                                        "ascending",
                                        "descending",
                                        "random",
                                    )[i % 4],
                                    layout="strided" if i % 2 else "contiguous",
                                )
                elif dtype != "int32" or op in ("copy", "sort", "gather"):
                    add(
                        op,
                        (128, 128) if op == "matmul" else (17, 4097),
                        dtype=dtype,
                        pattern="alternating",
                    )
        if "matmul" in config.operators:
            add("matmul", (511, 511), pattern="random")
    return result


def plan(config: Config) -> dict:
    from omnismi import __version__

    selected = cases(config)
    report = {
        "schema_version": 1,
        "report_type": "hardware_selftest",
        "tool_version": __version__,
        "status": "INCONCLUSIVE",
        "executed": False,
        "complete": False,
        "config": asdict(config),
        "cases": [asdict(case) for case in selected],
        "coverage": {
            "planned_cases": len(selected),
            "completed_cases": 0,
            "physical_units": {
                "status": "UNKNOWN",
                "observed_ids": [],
                "expected_count": None,
            },
        },
        "hardware_fault_confirmed": False,
        "current_hardware_health": "INCONCLUSIVE",
        "limitations": [
            "PASS applies only to completed comparisons; "
            "it does not certify hardware health.",
            "Library kernels cannot prove coverage of every SM/CU, ALU, "
            "tensor core, memory bank or link.",
            "Runtime-visible device/partition only; runtime index is not "
            "the omnismi global index.",
            "No XID/RAS collection is required for comparison failures; "
            "event logs are not collected here.",
            "Tensor budget excludes framework/driver workspace "
            "and host reference arrays.",
            "Finite inputs only in this version; CPU reference also needs "
            "independent validation.",
        ],
    }
    if config.target:
        from .targets import target_profile

        report["target"] = target_profile(config.target)
    return report
