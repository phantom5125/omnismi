"""Offline accelerator error interpretation; no vendor SDK or network required."""

from omnismi.diagnostics.engine import decode_error, diagnose
from omnismi.diagnostics.parsers import parse_log, parse_ras_counts

__all__ = ["decode_error", "diagnose", "parse_log", "parse_ras_counts"]
