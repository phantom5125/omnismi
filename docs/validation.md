# Validation

Omnismi includes a local parity checker to compare Omnismi readings with direct vendor-library readings.
Today that parity tool supports NVIDIA and AMD GPU backends only.

## Command

```bash
python -m omnismi.validation.parity --vendor nvidia --samples 3
python -m omnismi.validation.parity --vendor amd --samples 3
```

## Default tolerances

- utilization: `<= 3.0` percentage points
- memory used: `<= 64 MiB`
- temperature: `<= 3.0 C`
- power: `<= 8.0 W`
- core clock: `<= 150 MHz`

## Output model

The tool prints CSV-like rows with:

- metric name
- status (`PASS` / `FAIL` / `SKIP`)
- max observed diff
- tolerance
- compared datapoint count

## Scope

- This check is local and manual by design in v1.x.
- It is intended for hardware bring-up and release validation.
- Google TPU currently exposes snapshot metrics without a direct parity collector.
