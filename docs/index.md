# Omnismi

Omnismi provides one compact API for reading GPU information and metrics across vendors.

## Design goals

- Unified API surface for NVIDIA and AMD.
- Minimal function names aligned with `psutil` style.
- Stable metric units: bytes, percent, Celsius, Watts, MHz.
- Graceful degradation when some metrics are unavailable.

## Supported vendors

- NVIDIA through `nvidia-ml-py` (module: `pynvml`)
- AMD through `amdsmi`

## Quick usage

```python
import omnismi as omi

print(omi.count())
for dev in omi.gpus():
    print(dev.info())
    print(dev.metrics())
```

## Stability

Omnismi `1.x` focuses on a small stable contract:

- `count()`
- `gpus()`
- `gpu(index)`
- `GPU.info()`
- `GPU.metrics()`
