"""Tests for hardware detection logic on Linux."""

import sys
import os
from unittest.mock import patch
from omnismi.backends.amd import AmdBackend
from omnismi.backends.nvidia import NvidiaBackend

def test_amd_hardware_detection_linux():
    backend = AmdBackend()
    
    with patch("sys.platform", "linux"):
        with patch("os.path.exists") as mock_exists:
            # Case 1: Hardware exists
            mock_exists.side_effect = lambda p: p == "/sys/class/kfd"
            # We also need to mock _handles to avoid actual import
            with patch.object(AmdBackend, "_handles", return_value=["h0"]):
                assert backend.available() is True
            
            # Case 2: Hardware missing
            mock_exists.side_effect = lambda p: False
            assert backend.available() is False

def test_nvidia_hardware_detection_linux():
    backend = NvidiaBackend()
    
    with patch("sys.platform", "linux"):
        with patch("os.path.exists") as mock_exists:
            # Case 1: Hardware exists
            mock_exists.side_effect = lambda p: p == "/dev/nvidiactl"
            # We also need to mock _ensure_initialized to avoid actual import
            with patch.object(NvidiaBackend, "_ensure_initialized", return_value=True):
                backend._nvml = __import__("unittest.mock").mock.Mock()
                backend._nvml.nvmlDeviceGetCount.return_value = 1
                assert backend.available() is True
            
            # Case 2: Hardware missing
            mock_exists.side_effect = lambda p: False
            assert backend.available() is False

def test_detection_skipped_on_non_linux():
    amd_backend = AmdBackend()
    nv_backend = NvidiaBackend()
    
    with patch("sys.platform", "darwin"):
        with patch("os.path.exists") as mock_exists:
            # Should NOT call os.path.exists for these paths
            assert amd_backend.available() is False # Because import fails on Darwin
            assert nv_backend.available() is False # Because import fails on Darwin
            
            # Verify mock_exists was not called with linux paths
            for call in mock_exists.call_args_list:
                assert "/sys/class" not in call[0][0]
                assert "/dev/nvidia" not in call[0][0]
