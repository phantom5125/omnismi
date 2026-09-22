# Synthetic performance comparison example

These values test arithmetic only; they are not a GPU performance baseline.

```bash
omnismi perf-doctor --input examples/performance/synthetic-measurement.json --baseline examples/performance/synthetic-baseline.json
```

Expected: 80% of the synthetic sustained baseline, 40% of the synthetic peak,
WARN (exit 1) under the supplied test policy. Use actual measured baselines,
provenance and matching run conditions for real comparisons.
