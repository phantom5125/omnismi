# Performance expectations and perf-doctor

Status: offline comparison, baseline authoring and explicit bounded bandwidth/compute
probes are implemented. Real shared hardware baselines require recorded runs.

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
are not hardware reference values. File inputs are bounded to 1 MiB; offline `--input` never accesses a device.
Explicit live execution and baseline authoring are documented below.

## Live measurements and maintained baselines

```bash
omnismi perf-doctor --run bandwidth --vendor nvidia --device 0 --memory-mib 64 --repeats 5 --timeout 30 --context conditions.json --save-measurement run1.json
omnismi perf-doctor --run compute --vendor nvidia --device 0 --memory-mib 64 --timeout 30 --context conditions.json --save-measurement compute1.json
omnismi perf-doctor --build-baseline lab-copy --measurement run1.json --measurement run2.json --policy policy.json > baseline.json
omnismi perf-doctor --input fresh-run.json --baseline baseline.json
```

Each live call runs in a disposable child process with a whole-operation deadline
(0..600 seconds, exclusive lower bound), combined 1-MiB output budget and process
group cleanup. Only explicit `--run` allocates accelerator tensors. Runtime-local
indexes are not management/global Omnismi indexes. Missing runtimes, wrong vendor,
allocation errors and timeouts are INCONCLUSIVE; observed incorrect results are FAIL.

The tensor budget is 1..4096 MiB across three primary float32 buffers. Runtime
context, cached allocations and library workspace overhead are outside that budget.
Copy uses read+write bytes; triad uses two reads plus one write. Compute is dense
FP32 matrix multiplication with 2*N^3 FLOPs per iteration, dimensions derived from
the budget and capped at 2048. NVIDIA torch requests highest FP32 precision and
disables TF32 for compute. The exact probe/version is part of the signature.
These are portable host-timed synchronized probes, not vendor peak-kernel benchmarks.
Small buffers may fit in cache; do not compare them to a different memory regime.

The worker checks copy/vector correctness before timing, warms up, and retains
2..100 repeated samples with mean, sample standard deviation and coefficient of
variation. A run produces one measurement with a unique run ID. Distinct live calls
are needed to build a baseline; inner timing repeats are not independent run IDs.

Runtime captures vendor, model, probe/version, pattern, dtype, buffer size, byte/FLOP
convention, runtime/version and device count. Supply actual remaining conditions:
form_factor, partition, memory_mode, driver_version, power_limit_w and clock_policy.
Do not fill them by copying the desired baseline. `--context` cannot override
observed values. Without conditions or a baseline the measurement is still saved,
but comparison is INCONCLUSIVE. An existing output file is never overwritten.

Example policy (operator-selected, not a universal hardware recommendation):

```json
{"fail_below_percent":60,"pass_at_least_percent":90,"rationale":"Thresholds approved for this specific lab workload."}
```

`--build-baseline ID` requires 2..1000 positive measurements with exact matching
signatures, units and unique source IDs. It retains complete input measurements,
uses their mean as expected sustained performance and stores sample standard
deviation. Unknown conditions, repeated IDs, mixed workloads or nonfinite values
are rejected. Optional `--theoretical-peak reference.json` adds a separately sourced
reference; `--policy policy.json` supplies classification thresholds. Without a
policy the ratios can be reported but no pass threshold is invented.

Python: `omnismi.baselines.build_baseline` and `omnismi.probe_runtime.run_probe`.
NVIDIA/AMD torch and modern torch_mlu are supported runtime boundaries; SAIL active
compute remains gated until its runtime identity/API is verified. No SDK or torch
package is installed automatically.

The included examples are synthetic arithmetic fixtures, never real GPU reference
values. Publish maintained hardware baselines only after collecting actual repeated
runs with model/driver/runtime, power/clock/partition conditions and raw samples.
