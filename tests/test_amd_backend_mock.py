"""AMD backend tests with mocked amdsmi bindings."""

from __future__ import annotations

from omnismi.backends.amd import AmdBackend


class _Enum:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeAMDSMI:
    AmdSmiTemperatureType = _Enum(EDGE=1)
    AmdSmiTemperatureMetric = _Enum(CURRENT=1)
    AmdSmiClkType = _Enum(SYS=1, MEM=2)

    def __init__(self) -> None:
        self.shutdown_called = False

    def amdsmi_init(self) -> None:
        return None

    def amdsmi_shut_down(self) -> None:
        self.shutdown_called = True

    def amdsmi_get_processor_handles(self):
        return ["h0"]

    def amdsmi_get_gpu_asic_info(self, handle):
        return {
            "market_name": "MI300X",
            "asic_serial": "SERIAL-1",
        }

    def amdsmi_get_gpu_driver_info(self, handle):
        return {
            "driver_version": "6.4.2",
        }

    def amdsmi_get_gpu_vram_usage(self, handle):
        return {
            "vram_total": 192 * 1024**3,
            "vram_used": 20 * 1024**3,
        }

    def amdsmi_get_gpu_activity(self, handle):
        return {
            "gfx_activity": 70,
        }

    def amdsmi_get_temp_metric(self, handle, sensor, metric):
        return 67500

    def amdsmi_get_power_info(self, handle):
        return {
            "current_socket_power": 250000,
        }

    def amdsmi_get_clock_info(self, handle, clock_type):
        if clock_type == self.AmdSmiClkType.SYS:
            return {"clk": 1800}
        return {"clk": 2200}


def test_amd_backend_reads_expected_fields(monkeypatch) -> None:
    fake_amdsmi = _FakeAMDSMI()
    monkeypatch.setitem(__import__("sys").modules, "amdsmi", fake_amdsmi)

    backend = AmdBackend()
    assert backend.available() is True

    devices = backend.devices()
    assert len(devices) == 1

    info = backend.info(devices[0], index=0)
    assert info.vendor == "amd"
    assert info.name == "MI300X"
    assert info.driver == "6.4.2"
    assert info.memory_total_bytes == 192 * 1024**3

    metrics = backend.metrics(devices[0], index=0)
    assert metrics.utilization_percent == 70.0
    assert metrics.memory_used_bytes == 20 * 1024**3
    assert metrics.temperature_c == 67.5
    assert metrics.power_w == 250.0
    assert metrics.core_clock_mhz == 1800.0
    assert metrics.memory_clock_mhz == 2200.0

    backend.close()
    assert fake_amdsmi.shutdown_called is True
