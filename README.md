# Omnismi

<p align="center">
  <img src="docs/assets/OMNIsmi.svg" alt="Omnismi logo" width="320" />
</p>

<p align="center">
  <a href="https://pypi.org/project/omnismi/"><img src="https://img.shields.io/pypi/v/omnismi?label=PyPI&color=2d6cdf" alt="PyPI version" /></a>
  <a href="https://pypi.org/project/omnismi/"><img src="https://img.shields.io/pypi/pyversions/omnismi?label=Python" alt="Supported Python versions" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/pypi/l/omnismi?label=License" alt="License" /></a>
</p>

<p align="center">
  <strong>One compact API for accelerator inventory and metrics across NVIDIA GPUs, AMD GPUs, and experimental Google TPUs.</strong>
</p>

Cross-vendor accelerator observability for AI agents and Python scripts.
Omnismi provides a compact and stable Python API for reading accelerator information and metrics across vendors.
NVIDIA GPUs, AMD GPUs, and Google TPUs are supported today, with the Google TPU path marked experimental.

## Highlights

- One small public surface: `count`, `gpus`, `gpu`, `GPU.info()`, `GPU.metrics()`.
- Fixed normalized units across vendors: bytes, percent, Celsius, Watts, MHz.
- Graceful degradation by default: unavailable values become `None` instead of exceptions.
- Cached psutil-style GPU sampling plus `GPU.realtime()` for direct reads on NVIDIA and AMD.
- Ground-truth integrations with `nvidia-ml-py`, `amdsmi`, and `libtpu.sdk.tpumonitoring`.

## Quick Start

```python
import omnismi as omi

# 1) Count GPUs
gpu_count = omi.count()

# 2) Check whether GPU exists
has_gpu = gpu_count > 0

# 3) Get max total GPU memory (bytes) across visible devices
max_memory_bytes = max(
    (dev.info().memory_total_bytes or 0 for dev in omi.gpus()),
    default=0,
)

print(f"gpu_count={gpu_count}")
print(f"has_gpu={has_gpu}")
print(f"max_memory_bytes={max_memory_bytes}")
```

## Install

Omnismi core is lightweight and has no mandatory vendor dependency.
Pick the install command that matches your environment:

| Your environment | What to install | Command |
|---|---|---|
| No GPU / CI / just developing API integration | Core package only | `pip install omnismi` |
| NVIDIA GPUs only | Core + NVIDIA backend dependency | `pip install "omnismi[nvidia]"` |
| AMD GPUs only | Core + AMD backend dependency | `pip install "omnismi[amd]"` |
| Google TPU VM | Core + TPU backend dependency | `pip install "omnismi[tpu]"` |
| Mixed cluster or shared image | Core + NVIDIA + AMD + TPU dependencies | `pip install "omnismi[all]"` |

### Install From Local Source

```bash
# from repo root
python -m pip install -e ".[all]"
```

If you only need one vendor backend during local development:

```bash
python -m pip install -e ".[nvidia]"
# or
python -m pip install -e ".[amd]"
# or
python -m pip install -e ".[tpu]"
```

## Why Omnismi

- Unified API across vendors: `count`, `gpus`, `gpu`, `info`, `metrics`.
- Fixed normalized units: bytes, percent, Celsius, Watts, MHz.
- Graceful degradation: unavailable metrics return `None` instead of raising by default.
- NVIDIA and AMD both support psutil-style cached sampling plus `GPU.realtime()` for forced live reads.
- Google TPU support uses the TPU Monitoring Library through `libtpu.sdk.tpumonitoring`.
- Built-in parity checker to compare normalized output with direct vendor readings.

## Why not just torch/pynvml/amdsmi?

PyTorch memory APIs are useful in framework workflows, but are framework-scoped and not designed as a
cross-vendor observability contract for general runtime checks. Direct vendor bindings are essential,
but each has different lifecycle, naming, and compatibility details. Omnismi adds a stable cross-vendor
contract for agent preflight and application telemetry. See [docs/why-omnismi.md](docs/why-omnismi.md).

## Adapter Matrix (Ground Truth Libraries)

| Vendor | Runtime/Driver Stack | Ground Truth Library | Router Status |
|---|---|---|---|
| NVIDIA | CUDA + NVML | `nvidia-ml-py` | ✅ Supported |
| AMD | ROCm + AMD SMI | `amdsmi` | ✅ Supported |
| Google TPU | Cloud TPU VM + LibTPU SDK | `libtpu.sdk.tpumonitoring` | 🟡 Experimental |
| Intel | oneAPI + Level Zero | TBD | ⬜ Planned |
| Apple | Metal | TBD | ⬜ Planned |

Status legend:
- `✅ Supported`: Adapter path is integrated and maintained.
- `🟡 Partial`: Adapter is integrated but some metrics/features are incomplete.
- `🧪 Awaiting User Validation`: Adapter path exists; model/version evidence is still needed.
- `⬜ Planned`: Vendor adapter is not integrated yet.

## Hardware Validation Status

| Vendor | Model | Status | Evidence |
|---|---|---|---|
| NVIDIA | H20 | ✅ Verified | [v1.0.0 release note](CHANGELOG.md#100---2026-02-25) |
| AMD | MI300X | ✅ Verified | [v1.0.0 release note](CHANGELOG.md#100---2026-02-25) |
| Google TPU | Cloud TPU | 🧪 Awaiting User Validation | - |

See full matrix in [docs/compatibility.md](docs/compatibility.md).

## API

- `omi.count() -> int`
- `omi.gpus() -> list[GPU]`
- `omi.gpu(index: int) -> GPU | None`
- `GPU.info() -> GPUInfo`
- `GPU.metrics() -> GPUMetrics`
- `GPU.realtime() -> context manager` (force live reads when backend supports it)

Google TPU support currently reuses the existing `gpus()` / `GPUInfo` / `GPUMetrics` surface for API
compatibility even though the underlying accelerator is not a GPU.

## Current Support and Semantics

| Vendor | Status | Backend dependency | Read semantics |
|---|---|---|---|
| NVIDIA | Supported | `nvidia-ml-py` | Read-only, normalized units, cached by default, `GPU.realtime()` available |
| AMD | Supported | `amdsmi` | Read-only, normalized units, cached by default, `GPU.realtime()` available |
| Google TPU | Experimental | `libtpu` | Read-only snapshot metrics from TPU Monitoring Library; no Omnismi parity collector yet |
| Other vendors (Intel, Apple, etc.) | Planned | TBD | Same API contract (`count/gpus/gpu`, `info/metrics`) |

| Metric field | Unit | Semantic |
|---|---|---|
| `utilization_percent` | `%` | Vendor-reported primary compute/graphics engine activity percentage when available |
| `memory_used_bytes` / `memory_total_bytes` | `bytes` | Memory usage/total in bytes |
| `temperature_c` | `C` | Device temperature in Celsius |
| `power_w` | `W` | Power usage in Watts |
| `core_clock_mhz` / `memory_clock_mhz` | `MHz` | Core/memory clock when available |

`utilization_percent` is intentionally a cross-vendor activity signal. It is not an SM occupancy field on
NVIDIA or a CU occupancy field on AMD. Today Omnismi maps it to the closest top-level vendor activity metric
available, which is NVML `gpu` utilization for NVIDIA and `gfx_activity` / `gpu_util` for AMD.

### Sampling Semantics (NVIDIA and AMD)

- Omnismi initializes vendor libraries lazily on first backend use.
- `GPU.metrics()` is psutil-style for both NVIDIA and AMD: repeated calls return the latest cached sample instead of forcing a direct vendor read every time.
- A background sampler refreshes cached metrics periodically (default 0.5s interval).
- `GPU.realtime()` bypasses the cache and forces direct reads when the backend supports realtime mode. NVIDIA and AMD both implement it.
- On process exit or backend teardown, Omnismi stops the sampler and closes the vendor library.

Use realtime mode only when you explicitly need per-call direct reads:

```python
import omnismi as omi

dev = omi.gpu(0)
if dev is not None:
    with dev.realtime():
        live = dev.metrics()  # bypass cache for this call path
```

## Roadmap (Todo)

- Extend backend coverage to more accelerator vendors.
- Improve compatibility matrix depth across drivers/runtimes/architectures.
- Strengthen parity validation workflow and reporting, including non-GPU backends.
- Expand hardware-backed tests and reproducibility tooling.
- Keep API minimal while improving metric quality and consistency.

## Documentation

- API and usage docs: `docs/`
- Build docs locally: `mkdocs serve`
- GPU parity validation: `python -m omnismi.validation.parity --vendor nvidia --samples 3`

## Local Validation

```bash
# run unit tests
PYTHONPATH=src pytest -q

# compare normalized GPU output against direct vendor API
PYTHONPATH=src python -m omnismi.validation.parity --vendor nvidia --samples 3
PYTHONPATH=src python -m omnismi.validation.parity --vendor amd --samples 3
```

Google TPU support currently exposes local snapshot metrics only. A direct parity command for TPU is not yet available.

## License

MIT
