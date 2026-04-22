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

## Environment support goals

Omnismi aims to work not only on bare hosts, but also in the execution contexts
where accelerators are commonly consumed by applications and agents.

| Execution context | Goal | Notes |
|---|---|---|
| Supported GPU host | First-class | Primary validation path |
| Supported GPU container | First-class | Must reflect the container-visible device set |
| Kubernetes GPU pod / device-plugin environment | First-class | Must behave like the current pod sees, not like the whole host |
| CPU-only host or container | Safe empty result | No-device output is valid and should not be treated as a failure |

### Discovery parity expectation

For supported GPU vendors, Omnismi discovery should aim to match the visible
logical device set of the current execution environment.

In practice, this means:

- if the current container only sees a subset of host GPUs, Omnismi should only report that subset
- if the runtime can use a visible GPU, Omnismi should aim to surface it in the discovery layer
- if runtime visibility filters such as `CUDA_VISIBLE_DEVICES`, `NVIDIA_VISIBLE_DEVICES`, `HIP_VISIBLE_DEVICES`, or `ROCR_VISIBLE_DEVICES` are active, Omnismi should treat the process as runtime-scoped and report only that filtered set
- if PyTorch can enumerate visible GPUs in the current environment, Omnismi should aim to expose the same visible logical device set for the corresponding supported vendor

When Omnismi cannot match that expectation, the preferred behavior is to report
the mismatch explicitly through diagnostics rather than silently returning
misleading host-global data.

### Visibility controls and runtime scoping

Discovery and diagnostics should surface the active runtime-visibility controls
that shape what the current process can see.

Current examples include:

- `CUDA_VISIBLE_DEVICES`
- `NVIDIA_VISIBLE_DEVICES`
- `HIP_VISIBLE_DEVICES`
- `ROCR_VISIBLE_DEVICES`
- `GPU_DEVICE_ORDINAL`
- `TPU_VISIBLE_DEVICES`
- `TPU_VISIBLE_CHIPS`

These should be treated as execution-context metadata, not as hidden global
state. In other words, `omnismi --wide` and `omnismi doctor` should make it
clear when a container, pod, or environment variable is intentionally scoping
visible accelerators.

## Vendor/runtime matrix (v1 baseline)

| Vendor | Runtime/Driver | Architecture families | Tier |
|---|---|---|---|
| NVIDIA | CUDA/NVML-compatible driver | Hopper, Blackwell, and adjacent NVML-supported GPUs | Guaranteed on Linux x86_64 |
| AMD | ROCm/amdsmi-compatible stack | CDNA/RDNA families exposed by amdsmi | Guaranteed on Linux x86_64 |
| Google TPU | Cloud TPU VM + LibTPU SDK | Cloud TPU families exposed by the TPU Monitoring Library | Experimental |

## Adapter matrix (ground truth libraries)

| Vendor | Runtime/Driver Stack | Ground Truth Library | Router Status | Notes |
|---|---|---|---|---|
| NVIDIA | CUDA + NVML | `nvidia-ml-py` | ✅ Supported | Primary NVIDIA adapter in v1.x. |
| AMD | ROCm + AMD SMI | `amdsmi` | ✅ Supported | Primary AMD adapter in v1.x. |
| Google TPU | Cloud TPU VM + LibTPU SDK | `libtpu.sdk.tpumonitoring` | 🟡 Partial | Snapshot metrics only; direct parity tooling is not implemented yet. |
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
| Google TPU | Cloud TPU | TBD (awaiting user report) | `libtpu.sdk.tpumonitoring` adapter path implemented | `1.0.0rc` | 🧪 Awaiting User Validation | - | Direct parity tooling not implemented yet |
| Intel | Data Center GPU families | oneAPI + Level Zero (not integrated) | TBD | - | ⬜ Planned | - | Vendor adapter not integrated yet |

## Contributing validation evidence

Community validation is welcome. If you validate a model, submit evidence and we can promote it from
`🧪 Awaiting User Validation` to `✅ Verified`. See [CONTRIBUTING.md](../CONTRIBUTING.md) for
the required evidence template.

## Notes

- Metric availability varies by device, firmware, and permission model.
- Any unavailable metric is returned as `None` instead of raising by default.
- Unit normalization target is fixed: bytes, percent, Celsius, Watts, MHz.
