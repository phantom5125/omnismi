# Contributing

## Setup

```bash
python -m pip install -e ".[dev]" build twine
```

Optional docs setup:

```bash
python -m pip install -e ".[docs]"
```

## Local checks

```bash
python -m pytest -q
python -m mkdocs build --strict
python -m build
python -m twine check dist/*
```

Install the docs extra before the strict documentation build. Run Ruff and Black
on changed Python modules. Whole-repository lint has pre-existing findings; avoid
mixing unrelated cleanup into a scoped change. CI enforces lint on the onboarding
verification scripts and executes all regression tests.

To verify the actual distribution rather than the editable checkout:

```bash
python -m venv /tmp/omnismi-wheel-check
/tmp/omnismi-wheel-check/bin/python -m pip install --no-deps dist/omnismi-1.0.0-py3-none-any.whl
/tmp/omnismi-wheel-check/bin/python scripts/verify_v2_install.py
/tmp/omnismi-wheel-check/bin/python scripts/verify_quickstart.py
```

The current development distribution still uses version 1.0.0. Use a fresh test
environment or `--force-reinstall` after rebuilding. The quickstart checker runs
the tagged offline commands directly from README and both quickstart guides and
checks verdicts, exits and the 80%/40% arithmetic. Keep those examples runnable from
the repository root; do not add hardware workloads to the offline markers.

CI covers Linux Python 3.9, 3.10, 3.12 and 3.14, plus macOS Python 3.12. It also
builds documentation strictly and retains wheel/sdist and documentation artifacts
for review. These jobs validate software and synthetic native protocols, not the
real SDK ABI or physical devices. Hardware evidence is tracked separately below.

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
