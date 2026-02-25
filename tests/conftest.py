"""Test fixtures for Omnismi."""

from __future__ import annotations

import pytest

from omnismi.backends import registry


@pytest.fixture(autouse=True)
def _reset_backend_registry() -> None:
    registry._restore_default_factories_for_tests()
    yield
    registry._restore_default_factories_for_tests()


@pytest.fixture
def backend_factories():
    def _set(factories):
        registry._set_backend_factories_for_tests(factories)

    return _set
