"""Independent host inputs and full-array correctness checks (no device oracle)."""

from __future__ import annotations

import hashlib

import numpy as np

from .catalog import Case


def quantize(value, dtype):
    value = np.asarray(value)
    if dtype == "bfloat16":
        bits = value.astype(np.float32).view(np.uint32)
        rounded = (bits + np.uint32(0x7FFF) + ((bits >> 16) & 1)) & np.uint32(
            0xFFFF0000
        )
        return rounded.view(np.float32)
    return value.astype(dtype)


def inputs(case: Case, seed: int):
    rng = np.random.default_rng(seed)
    shape = case.shape
    a = rng.integers(-64, 65, size=shape).astype(np.float64)
    if case.dtype != "int32":
        a /= 16
    if case.pattern == "ties":
        a = rng.integers(-2, 3, size=shape).astype(np.float64)
    elif case.pattern in ("ascending", "descending"):
        a = np.broadcast_to(np.arange(shape[1]) % 127, shape).astype(np.float64).copy()
        a.sort(axis=-1)
        if case.pattern == "descending":
            a = a[:, ::-1].copy()
    elif case.pattern == "near_ties":
        a = 1 + rng.integers(-16, 17, size=shape) * 2**-20
    elif case.pattern == "alternating":
        a = np.where(np.indices(shape)[1] % 2, -a, a)
    # Small integral matmuls have exact FP32 sums; low precision outputs use
    # a separately rounded CPU reference with a declared tolerance.
    if case.operator == "matmul":
        a = rng.integers(-2, 3, size=shape)
        b = rng.integers(-2, 3, size=shape)
    elif case.operator == "gather":
        b = np.broadcast_to(rng.permutation(shape[1]), shape).copy().astype(np.int64)
    else:
        b = rng.integers(-8, 9, size=shape)
    return quantize(a, case.dtype), (
        b if case.operator == "gather" else quantize(b, case.dtype)
    )


def fingerprint(a, b):
    digest = hashlib.sha256()
    for value in (a, b):
        digest.update(str((value.dtype.str, value.shape)).encode())
        digest.update(value.tobytes(order="C"))
    return digest.hexdigest()


def expected(case, a, b):
    op = case.operator
    if op in ("topk", "sort"):
        ordered = np.sort(a, axis=-1)
        if op == "topk":
            ordered = ordered[:, ::-1] if case.largest else ordered
            ordered = ordered[:, : case.k]
        return ordered.copy()
    if op == "copy":
        return a.copy()
    if op == "gather":
        return np.take_along_axis(a, b, axis=-1)
    a64, b64 = a.astype(np.float64), b.astype(np.float64)
    if op == "add":
        output = a64 + b64
    elif op == "mul":
        output = a64 * b64
    elif op == "sum":
        return a64.sum(axis=-1).astype(np.float32)
    elif op == "matmul":
        output = a64 @ b64
    else:
        raise ValueError(f"unknown operator: {op}")
    return quantize(output, case.dtype)


def compare(case, a, reference, actual, indices=None):
    actual = np.asarray(actual)
    result = {
        "status": "PASS",
        "comparison": "exact",
        "mismatch_count": 0,
        "examples": [],
    }

    def fail(reason, mask=None):
        result.update(status="FAIL", reason=reason)
        if mask is not None:
            coordinates = np.argwhere(mask)
            result["mismatch_count"] = int(len(coordinates))
            result["examples"] = [list(map(int, coord)) for coord in coordinates[:8]]
        else:
            result["mismatch_count"] = 1
        return result

    if actual.shape != reference.shape:
        return fail("output_shape_mismatch")
    if not np.isfinite(actual).all():
        return fail("nonfinite_output", ~np.isfinite(actual))
    if case.operator in ("sort", "topk"):
        if indices is None:
            return fail("missing_indices")
        indices = np.asarray(indices)
        if indices.shape != actual.shape or not np.issubdtype(
            indices.dtype, np.integer
        ):
            return fail("invalid_index_shape_or_dtype")
        invalid = (indices < 0) | (indices >= a.shape[-1])
        if invalid.any():
            return fail("index_out_of_bounds", invalid)
        if np.any(np.diff(np.sort(indices, axis=-1), axis=-1) == 0):
            return fail("duplicate_indices")
        selected = np.take_along_axis(a, indices, axis=-1)
        if not np.array_equal(actual, selected):
            return fail("value_index_disagreement", actual != selected)
        # Compare value multisets for unsorted topk. Tied indices may differ
        # legally; uniqueness and input correspondence above still must hold.
        if case.operator == "topk" and not case.sorted:
            reference = np.sort(reference, axis=-1)
            actual = np.sort(actual, axis=-1)
    rtol, atol = 0.0, 0.0
    if case.operator == "matmul" and case.dtype in ("float16", "bfloat16"):
        rtol = {"float16": 0.001, "bfloat16": 0.008}[case.dtype]
        result.update(comparison="tolerance", rtol=rtol, atol=atol)
    close = np.isclose(actual, reference, rtol=rtol, atol=atol, equal_nan=False)
    if not close.all():
        return fail("cpu_reference_mismatch", ~close)
    return result
