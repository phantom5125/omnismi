# Contributing

## Setup

```bash
pip install -e ".[dev]"
```

Optional docs setup:

```bash
pip install -e ".[docs]"
```

## Local checks

```bash
PYTHONPATH=src pytest -q
ruff check src tests
black --check src tests
```

## Pull request requirements

- Keep changes scoped and focused.
- Add or update tests for behavioral changes.
- Update docs for public API, compatibility, or workflow changes.
- Do not add runtime dependency installation logic.

## Hardware validation contributions

If your PR adds a new validated model or upgrades a model status in the validation matrix, include all
evidence below:

- GPU model
- Vendor
- Driver/runtime versions
- OS/kernel version
- Python version
- Install extra used (for example `.[nvidia]`, `.[amd]`, or `.[all]`)
- `PYTHONPATH=src pytest -q` result
- `PYTHONPATH=src python -m omnismi.validation.parity --vendor <vendor> --samples 5` output
- Minimal GPU read script output (`count`, `gpus`, one `info`, one `metrics`)

Review policy:

- Any model marked `✅ Verified` must include evidence in the PR.
- Without evidence, the model can only be listed as `🧪 Awaiting User Validation`.
- A model can be promoted from `🧪 Awaiting User Validation` to `✅ Verified` once evidence is complete.
- Keep this statement explicit in documentation updates: `🧪 Awaiting User Validation` does NOT mean unsupported.

## Issue reporting

Include:

- GPU vendor/model
- driver/runtime versions
- Python version
- minimal reproduction snippet
