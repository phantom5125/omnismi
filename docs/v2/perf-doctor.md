# Performance expectations and perf-doctor

Status: offline evaluator and existing BenchReport import implemented on this
branch; no built-in hardware baseline, new probe runner or real-device validation.

## Available now

```bash
omnismi perf-doctor --input measurement.json --baseline baseline.json
omnismi perf-doctor --input bench-report.json --baseline baseline.json --context conditions.json --result-id bandwidth-0-0
```

Python: `from omnismi.performance import evaluate_performance, measurement_from_bench`.
Each comparison returns JSON with independent expected-sustained/theoretical-peak
percentages, exact signature mismatches, provenance and threshold-policy evidence.
New-command exits: 0 PASS, 1 WARN, 2 FAIL, 3 INCONCLUSIVE, 64 invalid input.

Version 1 measurement fields: `schema_version`, `metric` (`memory_bandwidth` or
`compute_throughput`), `unit` (`bytes/s` or `FLOP/s`), `value`, `signature`, `source`.
A source needs an `id` and `description`; `url` is optional and never fetched.

Baseline fields: `schema_version`, `baseline_id`, `metric`, `signature`,
`references` and optional `policy`. Each reference (`expected_sustained` or
`theoretical_peak`) needs positive finite `value`, matching `unit` and `source`.
Sustained references additionally need `sample_count >= 2`, nonnegative
`standard_deviation` in the same unit, and nonempty `run_ids`. These are provenance
requirements, not certification of user-supplied data.

`policy` supplies `fail_below_percent`, `pass_at_least_percent` and `rationale`,
with 0 <= fail < pass <= 100. Values below fail are FAIL; values at or above pass
are PASS; intermediate values are WARN. Without policy, ratios remain available
but the result is INCONCLUSIVE. Above-theoretical measurements also become
INCONCLUSIVE. Values above 100% are preserved, with an explicit review reason.

Required matching signature fields: vendor, sku, form_factor, partition,
memory_mode, probe, probe_version, pattern, dtype, buffer_bytes, byte_convention,
runtime, runtime_version, driver_version, device_count, power_limit_w, clock_policy.
Unknown/missing values block comparison. No implicit GB/GiB conversion or SKU alias
matching occurs. `baseline_missing` is explicit; there are no default thresholds.

Existing BenchReport input imports one successful bandwidth result. Multi-result
reports need `--result-id`. It verifies byte accounting, preserves captured vendor,
driver and probe parameters, and leaves uncaptured conditions unknown. `--context`
may fill missing signature fields but cannot override recorded observations.
For imported reports the probe version is `omnismi/<version>/torch-v1` and byte
convention is `read_plus_write`. Context must come from actual run conditions;
missing values are never copied from the baseline merely to make them match.

See `examples/performance/` for explicitly synthetic arithmetic examples. They
are not hardware reference values. File inputs are bounded to 1 MiB; no benchmark
or device access occurs in this command. The planned `--run` path below is not yet
implemented.

## User-facing contract

```text
omnismi perf-doctor --input bench-report.json --baseline baseline.json
omnismi perf-doctor --run bandwidth --profile h100-pcie-80gb
```

Proposed Python: `evaluate_performance(measurement, baseline)`. Offline evaluation
is independent of device access. `--run` explicitly executes a bounded workload
through the existing bandwidth probe. Matmul and multi-device transfer probes are
later additions with their own metric definitions.

## Denominators and comparability

Report separately `percent_of_theoretical_peak` and `percent_of_expected_sustained`.
Neither is accelerator utilization. Compute 100 * observed / reference only with
positive finite, unit-compatible references and a matching benchmark signature.
Do not clip values above 100%; flag the comparison for review. Do not fabricate an
80% threshold from a marketing bandwidth number. Missing or mismatched baselines
produce INCONCLUSIVE, never FAIL.

Baseline identity includes SKU/form factor, partition/MIG mode, memory mode,
benchmark/version, kernel/pattern, dtype, buffer size, read/write byte convention,
runtime/version, device count, power limit and clock policy. Record collection
conditions, source runs, sample count and dispersion. Mark essential mismatches
ineligible; any tolerated difference is explicit and justified in baseline metadata.

For copy, clearly state whether both read and write bytes are counted. Separate
GB/s from GiB/s, dense from sparse math, and host-device from device-memory bandwidth.
A theoretical profile is a specification; a sustained baseline is measured evidence.
Neither comes from guessing the device name or reusing a different GPU's result.

## Implementation sequence

1. `performance/models.py`: versioned measurement and baseline records, provenance,
   comparability requirements and threshold policy. Reuse existing bench evidence.
2. `performance/evaluate.py`: pure comparison, denominator validation, explicit
   PASS/WARN/FAIL policy supplied by the baseline, and INCONCLUSIVE reasons.
3. `performance/baselines/`: reviewed sustained baselines with raw-run provenance;
   initially allow user-provided baselines until validated shared data exists.
4. CLI offline evaluation, then opt-in repeated probe with warmup, synchronization,
   bounded memory/time, variance and interference reporting.
5. Optional topology/diagnostics evidence explains possible causes of a low result;
   percentage alone never asserts a faulty unit. Record temperature/power trends
   where observable, and distinguish throttling suspicion from observed limiting.

## Acceptance

Tests cover reference zero/negative/NaN/infinity, missing metrics, incompatible
units/patterns/dtypes/partition modes, threshold boundaries and >100% observations.
Validate output against independently calculated fixtures. Baselines require
repeatable real-device measurements before becoming built-in recommendations.
Regression-test existing `bench bandwidth` behavior and no-vendor operation.
