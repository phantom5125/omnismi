"""Real CPU framework adapter tests; these are NOT accelerator certifications."""

from __future__ import annotations

import pytest

from omnismi.selftest.backends import JaxBackend, TorchBackend
from omnismi.selftest.catalog import Case, Config, cases
from omnismi.selftest.reference import compare, expected, inputs, quantize


@pytest.mark.parametrize("framework", ["torch", "jax"])
def test_real_framework_cpu_contracts(framework):
    pytest.importorskip(framework)
    backend = (TorchBackend if framework == "torch" else JaxBackend)._for_cpu_tests()
    selected = cases(Config("nvidia" if framework == "torch" else "google"))
    for dtype in ("float16", "bfloat16", "int32"):
        selected.append(Case(f"cpu-{dtype}-topk", "topk", (7, 257), dtype=dtype, k=32))
        selected.append(Case(f"cpu-{dtype}-sort", "sort", (7, 257), dtype=dtype))
        if dtype != "int32":
            selected.append(
                Case(f"cpu-{dtype}-matmul", "matmul", (64, 64), dtype=dtype)
            )
    for case in selected:
        a, b = inputs(case, 123)
        reference = expected(case, a, b)
        actual, indices = backend.execute(case, a, b)
        result = compare(case, a, reference, actual, indices)
        assert result["status"] == "PASS", (framework, case, result)


def test_bfloat16_reference_matches_torch_cpu():
    torch = pytest.importorskip("torch")
    import numpy as np

    a = np.random.default_rng(12).uniform(-100, 100, size=4096).astype(np.float32)
    expected_bits = torch.tensor(a).to(torch.bfloat16).float().numpy()
    np.testing.assert_array_equal(quantize(a, "bfloat16"), expected_bits)


def test_cli_never_offers_cpu_fallback(capsys):
    from omnismi.cli import main

    with pytest.raises(SystemExit):
        main(["self-test", "--run", "--vendor", "cpu"])
    assert "invalid choice" in capsys.readouterr().err
