"""Tests for GPU detector."""

import pytest

from omnismi.core.detector import detect_gpus, get_available_vendors


class TestDetector:
    """Test GPU detection functionality."""

    def test_detect_gpus_returns_list(self):
        """detect_gpus should return a list."""
        result = detect_gpus()
        assert isinstance(result, list)

    def test_get_available_vendors_returns_list(self):
        """get_available_vendors should return a list."""
        result = get_available_vendors()
        assert isinstance(result, list)

    def test_gpu_info_has_required_fields(self):
        """Each GPU should have required fields."""
        gpus = detect_gpus()
        for gpu in gpus:
            assert hasattr(gpu, "id")
            assert hasattr(gpu, "name")
            assert hasattr(gpu, "vendor")
