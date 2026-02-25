"""Behavior tests when no backend is available."""

from __future__ import annotations

import omnismi as omi


def test_no_backend_returns_empty_results(backend_factories) -> None:
    backend_factories([])

    assert omi.count() == 0
    assert omi.gpus() == []
    assert omi.gpu(0) is None
