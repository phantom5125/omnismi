# Validation

Omnismi currently has two different validation-oriented workflows:

- `omnismi validate-spec`
  Compare the current visible device inventory against a curated profile such as
  `h100-pcie-80gb` or `mi300x-192gb` and emit `PASS/WARN/FAIL/INCONCLUSIVE`.
- `python -m omnismi.validation.parity`
  Compare Omnismi readings with direct vendor-library readings on the same
  machine. Today this parity tool supports NVIDIA and AMD GPU backends only.

## `validate-spec`

Example commands:

```bash
omnismi validate-spec --profile h100-pcie-80gb
omnismi validate-spec --profile mi300x-192gb -o json
```

Current built-in profiles:

- `h100-pcie-80gb`
- `mi300x-192gb`
- `tpu-v5p-32gb`

Current scope:

- compares vendor, curated model aliases, and reported total memory capacity
- reuses Omnismi's runtime-visible device scoping, including container and
  device-filter contexts
- does not yet include benchmark evidence from `omnismi bench`

## Parity checker

### Command

```bash
python -m omnismi.validation.parity --vendor nvidia --samples 3
python -m omnismi.validation.parity --vendor amd --samples 3
```

### Default tolerances

- utilization: `<= 3.0` percentage points
- memory used: `<= 64 MiB`
- temperature: `<= 3.0 C`
- power: `<= 8.0 W`
- core clock: `<= 150 MHz`

### Output model

The tool prints CSV-like rows with:

- metric name
- status (`PASS` / `FAIL` / `SKIP`)
- max observed diff
- tolerance
- compared datapoint count

### Scope

- This check is local and manual by design in v1.x.
- It is intended for hardware bring-up and release validation.
- Google TPU currently exposes snapshot metrics without a direct parity collector.
