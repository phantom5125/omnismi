# Agent CLI

`omnismi` ships a console script for agent/script preflight.

## Commands

- `omnismi preflight` — one-shot inventory + metrics gate (stable JSON on stdout)
- `omnismi inventory` — list accelerators
- `omnismi metrics` — snapshot metrics
- `omnismi version` — print package version

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | OK |
| 1 | Usage error (including invalid threshold arguments) |
| 2 | No visible accelerators |
| 3 | Threshold failure (`--min-gpus`, `--min-free-bytes` / `--min-free-gib`) |
| 10 | Backend error |

Usage errors write a message to stderr and no JSON to stdout. Help and version
requests exit 0. Counts and memory thresholds must be non-negative; GiB values
must also be finite and convertible to bytes. When both free-memory flags are
supplied, the stricter threshold applies.

## JSON snapshots

`preflight`, `inventory`, and `metrics` share `schema_version`, `command`, `ok`,
`exit_code`, `ts_ns` (Unix time in nanoseconds), `summary`, `devices`, `warnings`,
and `failures`. These fields are present for successful snapshots, empty
inventories, and backend errors. Additional fields describe each command.

`summary` includes `gpu_count`, `vendors`, `all_free_bytes_min`, and
`busy_gpu_count`. Unknown free memory and the unavailable busy count are `null`.
The `--human` flag also writes a one-line summary to stderr while preserving JSON
on stdout.

## Visibility

Honors `CUDA_VISIBLE_DEVICES` by default. Pass `--all-devices` to ignore it.

Integer device indexes, full UUIDs, and unique `GPU-` UUID prefixes are accepted;
UUID matching is case-insensitive. Bare UUID suffixes and ambiguous prefixes
cannot select a device. The first invalid or repeated identifier stops the list,
preserving only the devices selected before it. For example, `0,2,-1,1` selects
devices 0 and 2, remapped to logical indexes 0 and 1. An empty value selects none.
See NVIDIA's [CUDA environment variable reference](https://docs.nvidia.com/cuda/cuda-programming-guide/05-appendices/environment-variables.html).

## Notes

- `processes` and `topology` fields are reserved in the JSON schema but not implemented yet.
- `--require-idle` is accepted but not enforced until the processes API lands.
- Preflight uses one-shot `GPU.realtime()` metric reads (not a long-running sampler).
