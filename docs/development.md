# Development Guide

## Architecture

- `omnismi.api`: public API objects and functions
- `omnismi.models`: stable public dataclasses
- `omnismi.backends`: vendor implementations and registry
- `omnismi.normalize`: shared unit normalization rules
- `omnismi.validation`: local parity tooling

## Coding standards

- Keep the public API minimal and stable.
- Avoid `get_*` naming for read-only data retrieval.
- Backend failures must degrade gracefully (return partial metrics).
- Do not leak raw vendor exceptions to default user flow.

## Tests

```bash
PYTHONPATH=src pytest -q
```

## Long-running agent harness

Use the root harness files when an agent is working across multiple sessions:

- `app_spec.txt`: project goals, invariants, and non-goals
- `feature_list.json`: feature inventory plus verification commands
- `claude-progress.txt`: dated progress log and open issues
- `init.sh`: editable-install refresh plus smoke tests

Recommended loop:

```bash
./init.sh
```

Then pick one discrete item from `feature_list.json`, keep tests/docs in sync, and update `claude-progress.txt` before stopping.

Core test expectations:

- Public API contract behavior
- Backend isolation and registry behavior
- Unit normalization correctness
- Mocked backend integration for NVIDIA/AMD
- No-backend fallback behavior

## Documentation workflow

- Keep README short.
- Put detailed docs in `docs/`.
- Build docs locally with:

```bash
mkdocs serve
```
