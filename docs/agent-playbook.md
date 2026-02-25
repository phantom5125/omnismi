# Agent Playbook

This file defines contribution guardrails for autonomous agents.

## Fixed entrypoints

- Public API: `omnismi.count`, `omnismi.gpus`, `omnismi.gpu`
- GPU object methods: `GPU.info`, `GPU.metrics`
- Validation command: `python -m omnismi.validation.parity`

## Contract rules that must not be broken

- Keep metric units fixed: bytes, percent, Celsius, Watts, MHz.
- Keep unavailable metrics as `None`, not exceptions.
- Do not add `get_*` names to public API.
- Do not reintroduce runtime dependency installers.

## Change checklist

- Update tests for API and normalization behavior.
- Update docs for any public contract change.
- Verify no stale references to removed 0.x API names remain.
- Run `PYTHONPATH=src pytest -q` before finalizing.

## Backend implementation checklist

- Guard all vendor calls with local error handling.
- Normalize units before returning public models.
- Return deterministic field names and types.
- Keep backend-specific details out of public API docs.
