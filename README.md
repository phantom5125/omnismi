# Omnismi

<p align="center">
  <img src="OMNIsmi.svg" alt="Omnismi logo" width="320" />
</p>

Cross-vendor GPU observability for AI agents and Python apps (NVIDIA and AMD today).

Omnismi provides a compact and stable Python API for reading GPU information and metrics across vendors.
The long-term goal is broader vendor coverage without changing user-facing API contracts.

## Why Omnismi

- Unified API across vendors: `count`, `gpus`, `gpu`, `info`, `metrics`.
- Fixed normalized units: bytes, percent, Celsius, Watts, MHz.
- Graceful degradation: unavailable metrics return `None` instead of raising by default.
- NVIDIA psutil-style cached sampling plus `GPU.realtime()` for forced live reads.
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

See full matrix in [docs/compatibility.md](docs/compatibility.md).

## Install

Omnismi core is lightweight and has no mandatory vendor dependency.
Pick the install command that matches your environment:

| Your environment | What to install | Command |
|---|---|---|
| No GPU / CI / just developing API integration | Core package only | `pip install omnismi` |
| NVIDIA GPUs only | Core + NVIDIA backend dependency | `pip install "omnismi[nvidia]"` |
| AMD GPUs only | Core + AMD backend dependency | `pip install "omnismi[amd]"` |
| Mixed cluster or shared image | Core + NVIDIA + AMD dependencies | `pip install "omnismi[all]"` |

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
```

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

## API

- `omi.count() -> int`
- `omi.gpus() -> list[GPU]`
- `omi.gpu(index: int) -> GPU | None`
- `GPU.info() -> GPUInfo`
- `GPU.metrics() -> GPUMetrics`
- `GPU.realtime() -> context manager` (force live reads when backend supports it)

## Current Support and Semantics

| Vendor | Status | Backend dependency | Read semantics |
|---|---|---|---|
| NVIDIA | Supported | `nvidia-ml-py` | Read-only, normalized units, unavailable values return `None` |
| AMD | Supported | `amdsmi` | Read-only, normalized units, unavailable values return `None` |
| Other vendors (Intel, Apple, etc.) | Planned | TBD | Same API contract (`count/gpus/gpu`, `info/metrics`) |

| Metric field | Unit | Semantic |
|---|---|---|
| `utilization_percent` | `%` | GPU utilization percentage when available |
| `memory_used_bytes` / `memory_total_bytes` | `bytes` | Memory usage/total in bytes |
| `temperature_c` | `C` | Device temperature in Celsius |
| `power_w` | `W` | Power usage in Watts |
| `core_clock_mhz` / `memory_clock_mhz` | `MHz` | Core/memory clock when available |

### Sampling Semantics (NVIDIA)

- Omnismi initializes NVML lazily on first NVIDIA backend use (`nvmlInit`).
- `GPU.metrics()` is psutil-style for NVIDIA: repeated calls return the latest cached sample instead of reading NVML every call.
- A background sampler refreshes cached metrics periodically (default 0.5s interval).
- On process exit or backend teardown, Omnismi calls `nvmlShutdown()`.

Use realtime mode only when you explicitly need per-call direct reads:

```python
import omnismi as omi

dev = omi.gpu(0)
if dev is not None:
    with dev.realtime():
        live = dev.metrics()  # bypass cache for this call path
```

## Roadmap (Todo)

- Extend backend coverage to more GPU vendors.
- Improve compatibility matrix depth across drivers/runtimes/architectures.
- Strengthen parity validation workflow and reporting.
- Expand hardware-backed tests and reproducibility tooling.
- Keep API minimal while improving metric quality and consistency.

## Documentation

- API and usage docs: `docs/`
- Build docs locally: `mkdocs serve`
- Parity validation: `python -m omnismi.validation.parity --vendor nvidia --samples 3`

## Local Validation

```bash
# run unit tests
PYTHONPATH=src pytest -q

# compare normalized output against direct vendor API
PYTHONPATH=src python -m omnismi.validation.parity --vendor nvidia --samples 3
PYTHONPATH=src python -m omnismi.validation.parity --vendor amd --samples 3
```

## License

MIT
