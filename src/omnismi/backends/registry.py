"""Backend registry and lifecycle helpers."""

from __future__ import annotations

import atexit
import threading
from typing import Callable

from omnismi.backends.base import BaseBackend
from omnismi.backends.amd import AmdBackend
from omnismi.backends.google_tpu import GoogleTpuBackend
from omnismi.backends.nvidia import NvidiaBackend

BackendFactory = Callable[[], BaseBackend]

_DEFAULT_FACTORIES: tuple[BackendFactory, ...] = (
    NvidiaBackend,
    AmdBackend,
    GoogleTpuBackend,
)
_BACKEND_FACTORIES: tuple[BackendFactory, ...] = _DEFAULT_FACTORIES
_BACKENDS: list[BaseBackend] | None = None
_LOCK = threading.Lock()


def _build_backends() -> list[BaseBackend]:
    backends: list[BaseBackend] = []
    for factory in _BACKEND_FACTORIES:
        try:
            backends.append(factory())
        except Exception:
            continue
    return backends


def registered_backends() -> list[BaseBackend]:
    """Return all instantiated backends (available or not)."""
    global _BACKENDS

    with _LOCK:
        if _BACKENDS is None:
            _BACKENDS = _build_backends()
        return list(_BACKENDS)


def active_backends() -> list[BaseBackend]:
    """Return backends that are currently available on this host."""
    active: list[BaseBackend] = []

    for backend in registered_backends():
        try:
            if backend.available():
                active.append(backend)
        except Exception:
            continue

    return active


def close_all() -> None:
    """Close all instantiated backends."""
    global _BACKENDS

    with _LOCK:
        _close_all_unlocked()


def _close_all_unlocked() -> None:
    global _BACKENDS
    for backend in _BACKENDS or []:
        try:
            backend.close()
        except Exception:
            continue
    _BACKENDS = None


def _set_backend_factories_for_tests(factories: list[BackendFactory]) -> None:
    """Replace backend factories for tests and reset cache."""
    global _BACKEND_FACTORIES

    with _LOCK:
        _close_all_unlocked()
        _BACKEND_FACTORIES = tuple(factories)


def _restore_default_factories_for_tests() -> None:
    """Restore default backend factories for tests."""
    global _BACKEND_FACTORIES

    with _LOCK:
        _close_all_unlocked()
        _BACKEND_FACTORIES = _DEFAULT_FACTORIES


atexit.register(close_all)
