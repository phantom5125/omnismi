# Bench

The 2.0 preview implements `bench bandwidth`, `bench matmul` and `bench suite`.
Install the preview using the [quickstart](quickstart.md). These commands execute
accelerator workloads; management queries alone do not start them.

## Bounded matrix probe

```bash
omnismi bench matmul --vendor nvidia --device 0 --memory-mib 64 --repeats 5 --timeout 30
```

Required vendor: `nvidia`, `amd`, `alibaba` or `cambricon`. The device index belongs
to the selected compute runtime. The command checks copy/vector correctness, then
measures synchronized dense FP32 matrix multiplication, retains raw samples and
checks the final result. Dimensions derive from the memory budget and are capped
at 2048. Output is an `active_probe` JSON report, with FLOP/s using `2*N^3`.

NVIDIA/AMD use a matching torch runtime; MLU uses torch_mlu; PPU uses the
[SDK-compiled SAIL probe](v2/alibaba-ppu.md). NVIDIA torch disables TF32 and requests
highest FP32 precision. The SAIL path uses Omnismi's portable tiled kernel, not a
vendor BLAS/tensor-core peak benchmark.

## Bounded suite

```bash
omnismi bench suite --vendor nvidia --device 0 --memory-mib 64 --repeats 5 --timeout 90
```

The suite runs four probes sequentially: self-test, copy bandwidth, triad bandwidth
and matrix throughput. Each runs in an isolated process and retains its own
identity, checks and samples. All steps share one wall-time budget. A non-PASS
probe stops the sequence; remaining steps appear in `data.skipped` with reasons.

Both `matmul` and `suite` accept these options:

| Option | Meaning |
|---|---|
| `--vendor` | Required compute-runtime vendor |
| `--device` | Runtime-local index, default 0 |
| `--memory-mib` | Total primary device-buffer budget, 1–4096 MiB, default 64 |
| `--repeats` | 2–100 timing samples, default 5 |
| `--timeout` | Whole-command deadline, greater than 0 and at most 600 seconds; default 30 for matmul, 90 for suite |

Runtime context, allocator caches and library workspace are outside the primary
buffer budget. These commands emit JSON directly and do not take legacy
`--profile`, `--preset`, `--dtype` or `-o` flags.

Exits are 0 PASS, 1 WARN, 2 FAIL, 3 INCONCLUSIVE, 64 invalid input. A PASS covers
correctness of the executed checks. A missing runtime or timed-out operation is
INCONCLUSIVE; a numerical mismatch is FAIL without automatically diagnosing a
physical unit as defective. Whole-device health remains INCONCLUSIVE.

## Compare measured performance

Use [perf-doctor](v2/perf-doctor.md) for a fresh measurement, saved run and explicit
baseline comparison:

```bash
omnismi perf-doctor --run bandwidth --vendor nvidia --context conditions.json --save-measurement run.json
omnismi perf-doctor --input run.json --baseline baseline.json
```

Conditions must reflect the actual model, runtime, driver, power/clock and partition
state. A usable baseline requires independent recorded runs with matching
signatures. No universal pass percentage or hardware baseline is invented.
For a no-hardware example with provided files, start with the
[quickstart performance comparison](quickstart.md#try-the-performance-comparison).

## Legacy bandwidth report

The existing `bench bandwidth` interface remains available:

```bash
omnismi bench bandwidth --vendor nvidia --dtype fp32 --pattern copy --include-samples -o json
```

It uses Omnismi's management/global selection first, then a compatible NVIDIA/AMD
torch runtime, and emits the existing `BenchReport` in table, JSON or YAML form.
Its arguments and exit behavior differ from the new bounded commands:

- `--device` can repeat; `--all-devices` selects the current visible scope.
- `--pattern copy|triad`, `--dtype fp32|fp16|bf16`, `--buffer-bytes`, `--iterations`,
  `--warmup-seconds`, `--duration-seconds`, `--repeats` and `--include-samples` control
  the probe; `--runtime` accepts `auto` or `torch`.
- `--profile` attaches profile context. Raw throughput does not establish an
  expected-performance verdict; inspect the report and use `perf-doctor`.
- `-o table|json|yaml`, `--color` and `--no-color` control rendering.
- Inspect `summary.execution_status` and results; this older command may exit 0
  even when a probe reports an error.

Prefer `perf-doctor --run bandwidth` when a hard subprocess deadline and a
baseline-ready measurement are needed. Current flags are also available via
`omnismi bench bandwidth --help`.
