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

## Issue reporting

Include:

- GPU vendor/model
- driver/runtime versions
- Python version
- minimal reproduction snippet
