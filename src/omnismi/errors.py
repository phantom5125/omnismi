"""Unified error types for Omnismi."""

from __future__ import annotations


class OmnismiError(RuntimeError):
    """Base class for Omnismi user-facing errors."""


class BackendError(OmnismiError):
    """Raised when a backend cannot be initialized or queried."""


class ValidationError(OmnismiError):
    """Raised when validation tooling cannot proceed."""
