"""Normalization helpers to enforce cross-vendor metric units."""

from __future__ import annotations

from typing import Any

_NA_STRINGS = {"", "N/A", "NA", "NONE", "UNKNOWN"}


def _unwrap(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    return value


def _is_na(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().upper() in _NA_STRINGS
    return False


def _to_number(value: Any) -> float | None:
    value = _unwrap(value)
    if _is_na(value):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def normalize_text(value: Any) -> str | None:
    """Normalize text values with common not-available sentinels."""
    value = _unwrap(value)
    if _is_na(value):
        return None
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8", errors="replace")
        except Exception:
            return None
    text = str(value).strip()
    if _is_na(text):
        return None
    return text


def normalize_uuid(value: Any) -> str | None:
    """Normalize UUID-like identifiers to plain text."""
    return normalize_text(value)


def normalize_bytes(value: Any) -> int | None:
    """Normalize memory values to bytes."""
    number = _to_number(value)
    if number is None or number < 0:
        return None
    return int(number)


def normalize_percent(value: Any) -> float | None:
    """Normalize utilization values to percentage points (0..100)."""
    number = _to_number(value)
    if number is None or number < 0:
        return None
    if 0.0 <= number <= 1.0 and not float(number).is_integer():
        number *= 100.0
    if number > 100.0:
        return None
    return round(number, 3)


def normalize_temperature_c(value: Any, unit: str = "auto") -> float | None:
    """Normalize temperature values to Celsius."""
    number = _to_number(value)
    if number is None:
        return None
    if unit == "millicelsius" or (unit == "auto" and abs(number) > 1000.0):
        number /= 1000.0
    if number < -100.0 or number > 400.0:
        return None
    return round(number, 3)


def normalize_power_w(value: Any, unit: str = "auto") -> float | None:
    """Normalize power values to Watts."""
    number = _to_number(value)
    if number is None or number < 0:
        return None

    if unit == "w":
        return round(number, 4)
    if unit == "mw":
        return round(number / 1000.0, 4)
    if unit == "uw":
        return round(number / 1_000_000.0, 4)

    if unit != "auto":
        return None

    # Auto mode: choose the largest plausible value in Watts.
    candidates = [number, number / 1000.0, number / 1_000_000.0]
    plausible = [item for item in candidates if 0.0 <= item <= 2000.0]
    if not plausible:
        return None
    return round(max(plausible), 4)


def normalize_clock_mhz(value: Any) -> float | None:
    """Normalize clock rates to MHz."""
    number = _to_number(value)
    if number is None or number < 0:
        return None

    # Some APIs may return kHz or Hz instead of MHz.
    if number > 100_000_000.0:
        number /= 1_000_000.0
    elif number > 100_000.0:
        number /= 1000.0

    if number > 20_000.0:
        return None
    return round(number, 3)
