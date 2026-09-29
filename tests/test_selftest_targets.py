"""Presets are scoped plans, not claims of hardware validation."""

from dataclasses import replace

import pytest

from omnismi.selftest.catalog import Config, cases, plan
from omnismi.selftest.engine import execute
from omnismi.selftest.reference import expected
from omnismi.selftest.targets import matches_target, target_catalog, target_profile


@pytest.mark.parametrize(
    "identifier,vendor,name",
    [
        ("rtx-5090", "nvidia", "NVIDIA GeForce RTX 5090"),
        ("b300", "nvidia", "NVIDIA B300 SXM6 AC"),
        ("mi355x", "amd", "AMD Instinct MI355X"),
        ("tpu-v6e", "google", "TPU v6e"),
    ],
)
def test_target_profiles_match_identity_and_keep_unknown_coverage(
    identifier, vendor, name
):
    identity = {"vendor": vendor, "name": name}
    assert matches_target(identifier, identity)
    assert not matches_target(identifier, {**identity, "vendor": "wrong"})
    report = plan(Config(vendor, target=identifier))
    assert report["target"]["hardware_validation"] == "pending"
    assert report["coverage"]["physical_units"]["status"] == "UNKNOWN"
    assert not report["executed"]


def test_reject_other_models_and_conflicting_vendor():
    assert not matches_target("rtx-5090", {"vendor": "nvidia", "name": "RTX 5090D"})
    assert not matches_target("b300", {"vendor": "nvidia", "name": "NVIDIA B200"})
    assert not matches_target("tpu-v6e", {"vendor": "google", "name": "TPU v5p"})
    with pytest.raises(ValueError, match="vendor"):
        plan(Config("amd", target="rtx-5090"))
    with pytest.raises(ValueError, match="unknown target"):
        target_profile("unknown")


def test_tpu_preset_uses_bfloat16_without_changing_generic_contract():
    config = Config("google", profile="extended", target="tpu-v6e")
    assert {c.dtype for c in cases(config)} == {"float32", "bfloat16", "int32"}
    assert all(c.layout == "contiguous" for c in cases(config))
    assert "float16" in {c.dtype for c in cases(replace(config, target=None))}
    assert target_profile("tpu-v6e")["load_dtype"] == "bfloat16"
    assert len(target_catalog()["targets"]) == 4


def test_model_mismatch_stops_before_compute_or_telemetry():
    class Backend:
        identity = {"vendor": "nvidia", "name": "NVIDIA B200"}

        def execute(self, *_):
            pytest.fail("must not run on a mismatched device")

    class Sampler:
        def start(self):
            pytest.fail("must not start sampling on a mismatched device")

    report = execute(
        Config("nvidia", target="b300"),
        lambda _: None,
        backend=Backend(),
        sampler=Sampler(),
    )
    assert report["status"] == "INCONCLUSIVE"
    assert report["errors"][0]["reason"] == "target_device_mismatch"
    assert not report["results"] and not report["complete"]


def test_tpu_load_executes_with_preset_dtype():
    observed = []

    class Backend:
        identity = {"vendor": "google", "name": "TPU v6e", "uuid": None}

        def execute(self, case, a, b):
            observed.append(case)
            if case.id == "9000-matmul-load":
                # Stop this software-only test immediately after observing the load.
                raise RuntimeError("intentional fixture stop")
            return expected(case, a, b), None

    report = execute(
        Config(
            "google",
            target="tpu-v6e",
            profile="soak",
            operators=("matmul",),
            duration=0.01,
        ),
        lambda _: None,
        backend=Backend(),
    )
    load = next(c for c in observed if c.id == "9000-matmul-load")
    assert load.dtype == "bfloat16"
    assert report["status"] == "INCONCLUSIVE"
