# Product direction

**Omnismi is a cross-vendor accelerator tool for people and AI agents.** It helps
users understand what hardware is visible, whether the environment is ready,
what an error means, how performance compares with an appropriate baseline, and
whether observed calculations are correct.

The CLI is a primary product interface. Structured reports let agents and
programs use the same workflows from any language that can launch a process and
parse JSON. The Python API remains a supported integration surface. Python is
the current implementation and installation mechanism; it does not define the
product's scope. There is no standalone binary distribution today.

## What should work across hardware

The portability goal is to reuse **inspection, diagnosis and validation code**
across supported devices, changing device selection and deployment dependencies
where necessary. Callers should not need to parse each vendor's management-tool
output or rebuild its diagnostic rulebook.

| User task | Omnismi's portable contract | Differences that remain explicit |
|---|---|---|
| Identify available devices | Normalized inventory, identity and visibility | Physical device vs partition, management vs runtime indexes |
| Inspect current conditions | Common field names and units | Unsupported metrics, sampling intervals and freshness |
| Explain errors | Normalized findings, provenance and suggested checks | Vendor code namespaces, severity, firmware and source applicability |
| Check performance | Workload/condition metadata and baseline comparison | SKU, dtype, power settings, runtime and baseline suitability |
| Understand placement | Topology and affinity evidence | Available links, NUMA/NIC locality and incomplete observations |
| Test correctness | Reproducible cases, CPU references, failures and coverage | Supported operators, execution runtime and physical-unit evidence |

Common semantics do not imply equal capabilities. Missing measurements stay
null, unsupported execution is explicit, and incomplete evidence cannot become
a healthy-device verdict. A generic percentage must refer to a stated baseline
and compatible measurement conditions.

Current example: the Python `gpus()/info()/metrics()` calls are shared across
vendors. The command `omnismi --vendor nvidia -o json` can select another available
vendor using the same options and normalized inventory format. Active tests still
need the matching compute runtime and its local device index. The 2.1 SDC suite
does not yet execute on PPU; its declared unsupported result is part of the contract,
not evidence of portable execution on that hardware.

## Relationship to PyTorch and other frameworks

PyTorch already provides tensor computation, autograd, compilation, accelerator
integration, profiling and benchmark utilities. Omnismi should reuse those
capabilities where useful. Its focus is the common operational workflow and
evidence across vendors and runtimes, including processes that do not use
PyTorch. [PyTorch's documented components](https://docs.pytorch.org/docs/2.14/index.html)

For example, Omnismi may execute `torch.topk` to investigate correctness. The
framework owns the operator implementation; Omnismi owns the case matrix,
independent reference, timeout, failure archive and coverage statement. A SAIL
native worker or JAX execution adapter can serve the same diagnostic purpose
without introducing a new general-purpose tensor API.

Feature selection should preserve that division:

| Capability | Direction |
|---|---|
| Inventory, readiness, metrics, error interpretation, affinity evidence | Core Omnismi workflows |
| Correctness suites and condition-aware performance checks | Core validation workflows; reuse existing runtimes |
| Capability discovery and portable device identity/selection | Planned tool contracts; retain vendor-specific evidence |
| Framework environment summaries and profiler evidence import | Possible integrations when they improve a concrete diagnosis |
| General tensor operations, autograd, model execution, kernel compilation | Use existing frameworks; no parallel Omnismi compute API |
| Arbitrary model/code migration between accelerator vendors | Outside the portability promise; report compatibility constraints |
| Training orchestration or cluster scheduling | Consumers of Omnismi evidence, not the current product scope |

Native kernels are appropriate when a diagnostic needs physical-unit IDs,
memory patterns or coverage that frameworks cannot expose. Their purpose is
testing hardware, not building an application-compute platform.

## Human and agent interfaces

Both interfaces should derive their conclusions from the same report:

| For a person | For an agent or script |
|---|---|
| Concise summary, important findings and next steps | Versioned structured fields and command-specific status semantics |
| Device names and understandable units | Stable identity, units, source, freshness and scope |
| Show details only when needed | Bounded output with full evidence in artifacts when appropriate |
| Explain why a check could not run | Explicit unsupported/missing-dependency/insufficient-evidence reasons |
| Show what a workload will test | Inspectable plans and explicit workload execution |

This is the design target, not a claim that all commands already expose identical
flags or a shared JSON envelope. Today the default overview has table/JSON/YAML
views; newer diagnostics and the 2.1 self-test primarily return JSON. Legacy exit
behavior also differs. See [CLI](cli.md) for the actual contracts. A shared human
renderer, machine-readable capability discovery and report compatibility rules
are prioritized in the [roadmap](roadmap.md). An MCP wrapper may later expose
those same contracts; no MCP server is shipped now.

## How this shapes 2.1

The [self-test preview](v2.1/hardware-selftest.md) is an Omnismi workflow whose
execution adapters can use PyTorch, JAX or native vendor SDKs. Importing the
management API or generating a plan must not start a workload or require a
compute framework. Human output must eventually explain the same coverage gaps
that the JSON report records. A green CPU CI job is software evidence, not
physical-device validation.

When considering a feature, ask whether it removes repeated vendor-specific
operational code, produces actionable evidence for people and agents, and has
a truthful capability/validation story. Preserve the existing small Python API
while allowing the CLI, report formats, worker protocols and installation options
to grow around those user tasks.
