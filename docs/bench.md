# Bench

`omnismi bench` is the CLI surface for portable accelerator sanity checks.
Today the first `bandwidth` probe is implemented; `matmul` and `suite` remain
planned. This page describes both the current behavior and the intended longer-
term command layout.

## Goals

- Keep Omnismi core focused on discovery and normalized observability.
- Add portable, non-vendor benchmark probes that are easy to automate.
- Make default output readable for humans while keeping `json` and `yaml`
  outputs stable for agents and CI.
- Compare measured results against curated hardware profiles without turning
  Omnismi into a full profiler.

## Non-goals

- Replacing vendor profilers or deep performance-analysis suites
- Predicting model runtime from a full graph-analysis pipeline
- Chasing every vendor-specific benchmark mode in the core package

## Command layout

The initial CLI is expected to center on three subcommands:

```bash
omnismi bench bandwidth [flags]
omnismi bench matmul [flags]
omnismi bench suite [flags]
```

### `omnismi bench bandwidth`

Run a portable memory-bandwidth probe on one or more visible devices.

Current implementation notes:

- implemented with a portable `torch` runtime for NVIDIA and AMD devices when
  PyTorch can see the selected device
- uses Omnismi discovery scope first, so host/container/runtime-visible device
  filtering is preserved automatically
- emits a stable `BenchReport` in `table`, `json`, and `yaml`
- currently reports raw bandwidth evidence first and leaves verdicts
  `INCONCLUSIVE` until curated sustained-bandwidth thresholds are added to the
  profile registry

Expected use cases:

- verify that a rented machine is in the right bandwidth class
- detect throttling, power caps, or degraded runtime state
- compare repeated runs over time on the same node

Probe-specific flags:

- `--pattern copy|triad`
- `--dtype fp32|fp16|bf16`
- `--buffer-bytes BYTES`
- `--iterations N`

Notes:

- `copy` should be the simplest and most stable baseline.
- `triad` is useful as a more stressful STREAM-like pattern when supported.
- Output should report sustained device-local bandwidth, not a vendor-marketing peak.

### `omnismi bench matmul`

Run a portable GEMM or batched-GEMM throughput probe.

Current status: planned.

Expected use cases:

- sanity-check compute throughput by datatype
- confirm that tensor-core or matrix-core class execution is behaving as expected
- compare runtime-stack changes on the same hardware

Probe-specific flags:

- `--m INT`
- `--n INT`
- `--k INT`
- `--batch INT`
- `--dtype fp32|fp16|bf16|int8`
- `--iterations N`
- `--preset smoke|standard|saturating`

Notes:

- `--preset` should be the common entrypoint; explicit `m/n/k` flags override it.
- The benchmark should report achieved FLOP/s, not just wall time.
- When Omnismi can estimate arithmetic intensity for the chosen case, it should include that as a derived metric.

### `omnismi bench suite`

Run a curated set of benchmark cases and emit one consolidated report.

Current status: planned.

Expected use cases:

- one-shot acceptance test for a node or machine image
- attachable evidence for procurement, incident reports, or CI
- cluster bring-up and regression checks

Probe-specific flags:

- `--preset smoke|standard|extended`
- `--include bandwidth,matmul`
- `--profile NAME`
- `--fail-on warn|fail`

Notes:

- `suite` should reuse the same result schema as the individual probes.
- The suite command is where profile comparison becomes most useful.

## Common flags

These flags should be shared across `bandwidth`, `matmul`, and `suite` where relevant:

- `--device INDEX`
- `--all-devices`
- `--vendor nvidia|amd|google`
- `--profile NAME`
- `--runtime auto|torch`
- `--warmup-seconds FLOAT`
- `--duration-seconds FLOAT`
- `--repeats INT`
- `-o, --output table|json|yaml`
- `--quiet`
- `--color auto|always|never`
- `--no-color`
- `--include-samples`
- `--warn-below-ratio FLOAT`
- `--fail-below-ratio FLOAT`

Command rules:

- `table` is the default output format for interactive use.
- `json` and `yaml` serialize the same underlying report object.
- `--device` may be repeated.
- `--all-devices` and `--device` are mutually exclusive.
- `--profile` is optional; without it, benchmark results may still be valid but verdicts may become `INCONCLUSIVE`.
- Device scoping should follow the same host/container/runtime visibility rules as [`omnismi`](cli.md).

For the current `bandwidth` implementation:

- `--runtime auto|torch`, `--warmup-seconds`, `--duration-seconds`, `--repeats`,
  `--include-samples`, and the bandwidth-specific probe flags are implemented
- `--quiet`, `--warn-below-ratio`, and `--fail-below-ratio` remain planned

## Output formats

Omnismi should treat structured output as a first-class feature.

Recommended format behavior:

- `-o table`: human-oriented summary, color only on TTYs
- `-o json`: machine-oriented canonical serialization
- `-o yaml`: same object model as JSON, rendered as YAML for readability

Design notes:

- The schema should be versioned with `apiVersion`.
- New fields should be additive so agents can ignore unknown keys safely.
- Numeric benchmark metrics should use canonical base units in the structured schema:
  - bytes
  - bytes per second
  - flops per second
  - seconds
- Humanized units such as `GiB/s` or `TFLOP/s` belong in the `table` renderer, not as the primary schema contract.
- Shell redirection should be enough to save results:

```bash
omnismi bench suite --profile h100-pcie-80gb -o yaml > bench.yaml
omnismi bench matmul --preset standard -o json > matmul.json
```

Current implemented examples:

```bash
omnismi bench bandwidth
omnismi bench bandwidth --dtype bf16 --pattern triad
omnismi bench bandwidth --profile h100-pcie-80gb -o json
```

## Common report envelope

All structured outputs should follow one report envelope regardless of whether
the subcommand is `bandwidth`, `matmul`, or `suite`.

### Top-level shape

```yaml
apiVersion: omnismi/v1alpha1
kind: BenchReport
metadata:
  run_id: "6b862469-7f5d-4d0d-a9d6-1a5ff9d6a245"
  generated_at: "2026-04-23T03:11:02Z"
  omnismi_version: "1.1.0-dev"
command:
  argv:
    - "omnismi"
    - "bench"
    - "bandwidth"
    - "--profile"
    - "h100-pcie-80gb"
    - "-o"
    - "yaml"
  subcommand: "bandwidth"
  output: "yaml"
spec:
  devices: [0]
  all_devices: false
  vendor: "nvidia"
  profile: "h100-pcie-80gb"
  runtime: "auto"
  warmup_seconds: 1.0
  duration_seconds: 5.0
  repeats: 5
inventory:
  devices:
    - index: 0
      vendor: "nvidia"
      name: "NVIDIA H100 PCIe"
      uuid: "GPU-1234"
      driver: "550.54.15"
      memory_total_bytes: 85899345920
results: []
summary:
  execution_status: "success"
  verdict_status: "INCONCLUSIVE"
  result_count: 0
  pass_count: 0
  warn_count: 0
  fail_count: 0
  inconclusive_count: 0
```

### Top-level fields

- `apiVersion`: versioned schema identifier, starting with `omnismi/v1alpha1`
- `kind`: fixed as `BenchReport`
- `metadata`: report identity and generation metadata
- `command`: the invoked command shape
- `spec`: normalized benchmark request parameters
- `inventory`: Omnismi-discovered devices in scope for the run
- `results`: flat list of per-device, per-case benchmark outputs
- `summary`: overall execution and verdict rollup

## Result schema

`results` should stay flat instead of nesting deeply by probe. That makes it
easier for agents, CI, and data tooling to filter by `probe`, `device_index`,
or `case_name`.

### Common result fields

Each item in `results` should contain:

- `result_id`: stable identifier within a report
- `probe`: `bandwidth` or `matmul`
- `case_name`: user-facing case label such as `copy_fp32_1gib`
- `device_index`: Omnismi global device index
- `execution`:
  - `status`: `success|partial|error|skipped`
  - `started_at`
  - `ended_at`
  - `errors`
- `parameters`: probe-specific inputs after preset expansion
- `statistics`:
  - `sample_count`
  - `min_seconds`
  - `mean_seconds`
  - `median_seconds`
  - `p95_seconds`
  - `max_seconds`
  - `stdev_seconds`
- `metrics`: normalized measured and derived metrics
- `comparison`: optional comparison against the selected hardware profile
- `verdict`:
  - `status`: `PASS|WARN|FAIL|INCONCLUSIVE`
  - `reasons`

The current `bandwidth` implementation fills this schema with stable execution
and measurement data today, while leaving `comparison` and profile-aware
`verdict` thresholds intentionally conservative until more curated benchmark
baselines are added.

## Bandwidth result schema

Bandwidth probe results should use these `parameters` and `metrics` keys.

### `parameters`

- `pattern`
- `dtype`
- `buffer_bytes`
- `iterations`
- `bytes_per_iteration`

### `metrics`

- `bandwidth_bytes_per_s`
- `arithmetic_intensity_flops_per_byte`

For pure bandwidth patterns, `arithmetic_intensity_flops_per_byte` may be `0.0`
or omitted if not meaningful.

### Example

```yaml
results:
  - result_id: "bandwidth:0:copy_fp32_1gib"
    probe: "bandwidth"
    case_name: "copy_fp32_1gib"
    device_index: 0
    execution:
      status: "success"
      started_at: "2026-04-23T03:11:03Z"
      ended_at: "2026-04-23T03:11:09Z"
      errors: []
    parameters:
      pattern: "copy"
      dtype: "fp32"
      buffer_bytes: 1073741824
      iterations: 400
      bytes_per_iteration: 2147483648
    statistics:
      sample_count: 5
      min_seconds: 0.00108
      mean_seconds: 0.00112
      median_seconds: 0.00111
      p95_seconds: 0.00116
      max_seconds: 0.00117
      stdev_seconds: 0.00003
    metrics:
      bandwidth_bytes_per_s: 1917396114285.71
      arithmetic_intensity_flops_per_byte: 0.0
    comparison:
      profile: "h100-pcie-80gb"
      metric: "memory_bandwidth_bytes_per_s"
      expected: 2039000000000.0
      observed: 1917396114285.71
      observed_ratio: 0.9404
      warn_below_ratio: 0.80
      fail_below_ratio: 0.60
    verdict:
      status: "PASS"
      reasons:
        - "Observed sustained bandwidth is within the expected range for the selected profile."
```

## Matmul result schema

Matmul probe results should use these `parameters` and `metrics` keys.

### `parameters`

- `m`
- `n`
- `k`
- `batch`
- `dtype`
- `iterations`

### `metrics`

- `throughput_flops_per_s`
- `arithmetic_intensity_flops_per_byte`
- `flops_per_iteration`

### Example

```yaml
results:
  - result_id: "matmul:0:bf16_standard"
    probe: "matmul"
    case_name: "bf16_standard"
    device_index: 0
    execution:
      status: "success"
      started_at: "2026-04-23T03:12:00Z"
      ended_at: "2026-04-23T03:12:08Z"
      errors: []
    parameters:
      m: 8192
      n: 8192
      k: 8192
      batch: 1
      dtype: "bf16"
      iterations: 200
    statistics:
      sample_count: 5
      min_seconds: 0.00178
      mean_seconds: 0.00184
      median_seconds: 0.00183
      p95_seconds: 0.00189
      max_seconds: 0.00190
      stdev_seconds: 0.00004
    metrics:
      throughput_flops_per_s: 608934229508196.75
      arithmetic_intensity_flops_per_byte: 1365.33
      flops_per_iteration: 1099511627776
    comparison:
      profile: "h100-pcie-80gb"
      metric: "peak_bf16_flops_per_s"
      expected: 756000000000000.0
      observed: 608934229508196.75
      observed_ratio: 0.8055
      warn_below_ratio: 0.60
      fail_below_ratio: 0.35
    verdict:
      status: "PASS"
      reasons:
        - "Observed BF16 GEMM throughput is within the selected profile threshold."
```

## Summary schema

The `summary` object should make it easy to answer "did this node look healthy?"
without reprocessing every row.

Expected keys:

- `execution_status`: `success|partial|error`
- `verdict_status`: `PASS|WARN|FAIL|INCONCLUSIVE`
- `result_count`
- `pass_count`
- `warn_count`
- `fail_count`
- `inconclusive_count`
- `profile`
- `worst_result_id`
- `worst_observed_ratio`

`verdict_status` rules:

- `FAIL` if any result is `FAIL`
- `WARN` if there are no `FAIL` results and at least one `WARN`
- `PASS` if every completed result is `PASS`
- `INCONCLUSIVE` if no meaningful profile comparison was possible

## Design notes for implementation

- The benchmark layer should be optional and must not expand the minimal Python
  observability API.
- Structured output should share one object model across `json` and `yaml`.
- Table output is a projection of the structured report, not a separate contract.
- Missing runtime support should surface as `execution.status=error` with a
  human-readable message, while the overall report may still remain
  `INCONCLUSIVE` instead of `FAIL`.
