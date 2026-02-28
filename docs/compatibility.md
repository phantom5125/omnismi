# Compatibility

Omnismi normalizes values but does not hide platform/runtime constraints.

## Status legend

- `✅ Verified`: Real hardware validated with tests and parity checks.
- `🟡 Partial`: Adapter works, but one or more metrics/features are known to be partial.
- `🧪 Awaiting User Validation`: Adapter path exists; model/version evidence is pending.
- `⬜ Planned`: Not currently integrated.

`🧪 Awaiting User Validation` does NOT mean unsupported.

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

## Adapter matrix (ground truth libraries)

| Vendor | Runtime/Driver Stack | Ground Truth Library | Router Status | Notes |
|---|---|---|---|---|
| NVIDIA | CUDA + NVML | `nvidia-ml-py` | ✅ Supported | Primary NVIDIA adapter in v1.x. |
| AMD | ROCm + AMD SMI | `amdsmi` | ✅ Supported | Primary AMD adapter in v1.x. |
| Intel | oneAPI + Level Zero | TBD | ⬜ Planned | Future vendor onboarding. |
| Apple | Metal | TBD | ⬜ Planned | Future vendor onboarding. |

## Compatibility matrix (runtime + model)

| Vendor | Model | Driver/Runtime Version | Ground Truth Library Version | Omnismi Version | Status | Evidence | Failure Cause |
|---|---|---|---|---|
| NVIDIA | H20 | CUDA/NVML-compatible stack (validated) | `nvidia-ml-py` (validated) | `1.0.0rc` | ✅ Verified | [v1.0.0 release note](../CHANGELOG.md#100---2026-02-25) | - |
| NVIDIA | H100 | TBD (awaiting user report) | `nvidia-ml-py` adapter path implemented | `1.0.0rc` | 🧪 Awaiting User Validation | - | - |
| NVIDIA | H200 | TBD (awaiting user report) | `nvidia-ml-py` adapter path implemented | `1.0.0rc` | 🧪 Awaiting User Validation | - | - |
| NVIDIA | B200 | TBD (awaiting user report) | `nvidia-ml-py` adapter path implemented | `1.0.0rc` | 🧪 Awaiting User Validation | - | - |
| NVIDIA | RTX 4090 | TBD (awaiting user report) | `nvidia-ml-py` adapter path implemented | `1.0.0rc` | 🧪 Awaiting User Validation | - | - |
| AMD | MI300X | ROCm/amdsmi-compatible stack (validated) | `amdsmi` (validated) | `1.0.0rc` | ✅ Verified | [v1.0.0 release note](../CHANGELOG.md#100---2026-02-25) | - |
| AMD | MI250 | TBD (awaiting user report) | `amdsmi` adapter path implemented | `1.0.0rc` | 🧪 Awaiting User Validation | - | - |
| AMD | MI300A | TBD (awaiting user report) | `amdsmi` adapter path implemented | `1.0.0rc` | 🧪 Awaiting User Validation | - | - |
| AMD | MI325X | TBD (awaiting user report) | `amdsmi` adapter path implemented | `1.0.0rc` | 🧪 Awaiting User Validation | - | - |
| AMD | RX 7900 XTX | TBD (awaiting user report) | `amdsmi` adapter path implemented | `1.0.0rc` | 🧪 Awaiting User Validation | - | - |
| Intel | Data Center GPU families | oneAPI + Level Zero (not integrated) | TBD | - | ⬜ Planned | - | Vendor adapter not integrated yet |

## Contributing validation evidence

Community validation is welcome. If you validate a model, submit evidence and we can promote it from
`🧪 Awaiting User Validation` to `✅ Verified`. See [CONTRIBUTING.md](../CONTRIBUTING.md) for
the required evidence template.

## Notes

- Metric availability varies by device, firmware, and permission model.
- Any unavailable metric is returned as `None` instead of raising by default.
- Unit normalization target is fixed: bytes, percent, Celsius, Watts, MHz.
