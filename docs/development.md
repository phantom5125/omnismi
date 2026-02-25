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
