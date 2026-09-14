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
| 2 | No visible accelerators |
| 3 | Threshold failure (`--min-gpus`, `--min-free-bytes` / `--min-free-gib`) |
| 10 | Backend error |
| 1 / argparse 2 | Usage error |

## Visibility

Honors `CUDA_VISIBLE_DEVICES` by default. Pass `--all-devices` to ignore it.

## Notes

- `processes` and `topology` fields are reserved in the JSON schema but not implemented yet.
- `--require-idle` is accepted but not enforced until the processes API lands.
- Preflight uses one-shot `GPU.realtime()` metric reads (not a long-running sampler).
