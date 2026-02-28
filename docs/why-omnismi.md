# Why Omnismi

## Target users

- AI agent and coding-agent developers who need portable GPU preflight checks.
- Python application developers who want one GPU metrics API across mixed vendor environments.
- Platform engineers operating shared images or clusters that may include NVIDIA and AMD GPUs.

## Why torch memory APIs are not enough

PyTorch memory APIs are valuable for framework-level diagnosis, but they are scoped to the PyTorch
runtime and workflow. They are not intended to be a general cross-vendor observability contract for
non-PyTorch processes, mixed-runtime systems, or lightweight agent readiness checks.

## Why direct vendor bindings are not enough

Direct vendor bindings are the source of truth and Omnismi depends on them. However, each binding has
different API shapes, lifecycle requirements, and compatibility differences. Using those bindings
directly in app logic often creates vendor-specific branches and repeated normalization code.

## What Omnismi adds

- A stable cross-vendor API contract: `count`, `gpus`, `gpu`, `info`, `metrics`.
- Normalized metric units and field names for common telemetry workflows.
- Graceful degradation semantics: missing values are returned as `None`.
- A parity command to compare Omnismi output with direct vendor readings.
- Clear support-vs-validation semantics for production planning.

`🧪 Awaiting User Validation` does NOT mean unsupported.

## Non-goals

- Omnismi is not a full profiler or a complete replacement for vendor-native tooling.
- Omnismi does not hide platform, permission, or driver/runtime constraints.
- Omnismi does not guarantee that every metric is available on every device.
