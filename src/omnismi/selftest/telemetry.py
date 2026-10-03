"""Optional, UUID-attributed observations. Missing telemetry is never invented."""

from __future__ import annotations

import math
import threading
import time


class Sampler:
    def __init__(self, identity):
        self.identity = identity
        self._phase = ("baseline", time.time_ns())
        self.samples = []
        self.reason = "no_matching_runtime_uuid"
        self._stop = threading.Event()
        self._thread = None

    @property
    def phase(self):
        return self._phase[0]

    @phase.setter
    def phase(self, value):
        if value != self._phase[0]:
            self._phase = (value, time.time_ns())

    def start(self):
        if not self.identity.get("uuid"):
            return
        self._thread = threading.Thread(target=self._collect, daemon=True)
        self._thread.start()

    def _collect(self):
        from omnismi.api import gpus

        try:
            matched = []
            for gpu in gpus():
                info = gpu.info()
                if (
                    info.vendor == self.identity["vendor"]
                    and info.uuid == self.identity["uuid"]
                ):
                    matched.append(gpu)
            if len(matched) != 1:
                return
            gpu = matched[0]
            self.reason = "matched_runtime_uuid"
            last = 0
            with gpu.realtime():
                while not self._stop.is_set() and len(self.samples) < 7200:
                    phase, phase_start = self._phase
                    metric = gpu.metrics()
                    now = time.time_ns()
                    stamp = metric.timestamp_ns
                    if (
                        stamp > last
                        and stamp >= phase_start
                        and 0 <= now - stamp <= 2_000_000_000
                        and metric.power_w is not None
                        and math.isfinite(metric.power_w)
                        and metric.power_w >= 0
                        and (phase, phase_start) == self._phase
                    ):
                        temperature = metric.temperature_c
                        if temperature is not None and not math.isfinite(temperature):
                            temperature = None
                        self.samples.append(
                            {
                                "timestamp_ns": stamp,
                                "phase": phase,
                                "power_w": metric.power_w,
                                "temperature_c": temperature,
                            }
                        )
                        last = stamp
                    self._stop.wait(0.5)
        except Exception as exc:
            self.reason = f"telemetry_unavailable: {type(exc).__name__}"

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)

    def report(self, target=None):
        samples = list(self.samples)
        load = [item["power_w"] for item in samples if item["phase"] == "load"]
        hits = sum(value >= target for value in load) if target is not None else 0
        # This is an observed sample fraction, not a calibrated duty cycle.
        reached = target is not None and len(load) >= 3 and hits / len(load) >= 0.8
        return {
            "attribution": self.reason,
            "samples": samples,
            "target_w": target,
            "load_sample_count": len(load),
            "samples_at_or_above_target": hits,
            "target_observed": reached if target is not None else None,
            "peak_w": max((item["power_w"] for item in samples), default=None),
            "criterion": "at least 3 fresh load samples; at least 80% >= target",
            "limitations": "Software polling cannot resolve "
            "instantaneous power transients.",
        }
