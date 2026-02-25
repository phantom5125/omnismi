"""Normalization unit tests."""

from __future__ import annotations

from omnismi.normalize import (
    normalize_bytes,
    normalize_clock_mhz,
    normalize_percent,
    normalize_power_w,
    normalize_temperature_c,
)


def test_normalize_nvidia_power_mw_to_w() -> None:
    assert normalize_power_w(250000, unit="mw") == 250.0


def test_normalize_temperature_from_millicelsius() -> None:
    assert normalize_temperature_c(65500, unit="millicelsius") == 65.5


def test_normalize_clock_from_khz() -> None:
    assert normalize_clock_mhz(1410000) == 1410.0


def test_normalize_percent_fraction() -> None:
    assert normalize_percent(0.62) == 62.0


def test_normalize_bytes_invalid_values() -> None:
    assert normalize_bytes("N/A") is None
    assert normalize_bytes(-1) is None
    assert normalize_bytes(1024) == 1024
