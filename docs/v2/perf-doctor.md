# Performance expectations and perf-doctor

Status: planned; no curated sustained baseline or percentage verdict is shipped yet.

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
