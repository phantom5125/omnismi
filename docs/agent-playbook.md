# Agent Playbook

This file defines contribution guardrails for autonomous agents.

## Product direction

Omnismi is a cross-vendor accelerator tool for people and agents. The CLI and
structured reports are primary interfaces; the existing Python API remains
compatible. Read [product direction](why-omnismi.md) before expanding scope.

Prefer features that let callers reuse discovery, diagnosis, performance,
topology and validation workflows across hardware. Reuse PyTorch/JAX/vendor SDKs
for computation. General tensor APIs, autograd and model migration are outside
the tool's scope. Distinguish implemented adapters, planned capabilities and
real hardware validation in every user-facing claim.

## Long-running harness files

- `app_spec.txt`: root source of truth for product goals, invariants, and non-goals.
- `feature_list.json`: machine-readable feature catalog with statuses and verification commands.
- `claude-progress.txt`: append-only session log plus open issues.
- `init.sh`: bootstrap and validation entrypoint for each session.

Preferred session loop:

1. Read `app_spec.txt`, `feature_list.json`, and `claude-progress.txt`.
2. Run `./init.sh`.
3. Pick one discrete feature, validation item, or contract-hardening task.
4. Update tests/docs together with code.
5. Update `feature_list.json` and append a short note to `claude-progress.txt`.

## Fixed entrypoints

- Tool: `omnismi` / `python -m omnismi`; see [CLI contracts](cli.md).
- Reports: command-specific structured output, evidence and explicit coverage limits.
- Public API: `omnismi.count`, `omnismi.gpus`, `omnismi.gpu`
- GPU object methods: `GPU.info`, `GPU.metrics`
- Validation command: `python -m omnismi.validation.parity`

## Contract rules that must not be broken

- Keep metric units fixed: bytes, percent, Celsius, Watts, MHz.
- Keep unavailable metrics as `None`, not exceptions.
- Do not add `get_*` names to public API.
- Do not reintroduce runtime dependency installers.
- Keep plans and offline commands usable without a compute framework.
- Derive human summaries and machine output from the same diagnostic evidence.
- Preserve report compatibility and explicit unsupported/unknown outcomes.

## Change checklist

- Update tests for API and normalization behavior.
- Update docs for any public contract change.
- Update `feature_list.json` if a feature status or verification path changes.
- Append a short dated note to `claude-progress.txt` at the end of the session.
- Verify no stale references to removed 0.x API names remain.
- Run relevant tests for behavioral changes; use strict docs/example checks for documentation-only changes.

## Backend implementation checklist

- Guard all vendor calls with local error handling.
- Normalize units before returning public models.
- Return deterministic field names and types.
- Keep backend-specific details out of public API docs.
