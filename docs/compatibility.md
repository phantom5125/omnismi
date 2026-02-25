# Compatibility

Omnismi normalizes values but does not hide platform/runtime constraints.

## Support tiers

| Target | Tier | Notes |
|---|---|---|
| Linux x86_64 | Guaranteed | Primary CI and release target for v1.x |
| Linux ARM64 | Community | Accepted with contributor validation |
| Windows | Experimental | No official v1.x guarantee |
| macOS | Experimental | No official v1.x guarantee |

## Vendor/runtime matrix (v1 baseline)

| Vendor | Runtime/Driver | Architecture families | Tier |
|---|---|---|---|
| NVIDIA | CUDA/NVML-compatible driver | Hopper, Blackwell, and adjacent NVML-supported GPUs | Guaranteed on Linux x86_64 |
| AMD | ROCm/amdsmi-compatible stack | CDNA/RDNA families exposed by amdsmi | Guaranteed on Linux x86_64 |

## Notes

- Metric availability varies by device, firmware, and permission model.
- Any unavailable metric is returned as `None` instead of raising by default.
- Unit normalization target is fixed: bytes, percent, Celsius, Watts, MHz.
