# Agent Guide

Omnismi gives agents a bounded command-line interface for accelerator inventory,
telemetry, error interpretation, topology, and explicit correctness workloads.
Use the CLI when the agent should inspect the current execution environment;
use the [Python API](api.md) only when the application needs in-process access.

## Choose the smallest command that answers the question

| Task | Command | Side effects |
|---|---|---|
| List visible devices and telemetry | `omnismi -o json` | Read-only |
| Explain missing devices or metrics | `omnismi doctor -o json` | Read-only |
| Explain a recorded vendor error | `omnismi decode --vendor nvidia --namespace xid --code 48` | Offline |
| Interpret a captured log | `omnismi diagnose --input events.log` | Offline |
| Collect current hardware evidence | `omnismi diagnose --collect hardware --timeout 30` | Read-only collectors |
| Inspect device locality | `omnismi topology` | Read-only |
| Check numerical execution | `omnismi bench suite --vendor nvidia --device 0 --memory-mib 64 --timeout 90` | Allocates memory and runs workloads |

Do not turn an inventory or offline diagnosis into an active benchmark unless
the user intends to run that workload. Management indexes and compute-runtime
indexes can differ in containers and partitioned devices; retain the device
identity in each report instead of joining results by index alone.

## Parse reports without losing verdicts

The structured report commands `decode`, `diagnose`, `perf-doctor`, `topology`,
and `bench matmul/suite` write one JSON object to stdout. Their process exits
represent verdicts as well as execution failures:

| Exit | Meaning |
|---|---|
| 0 | PASS, or successful baseline construction |
| 1 | WARN |
| 2 | FAIL in the supplied evidence or executed checks |
| 3 | INCONCLUSIVE because evidence, runtime, support, or a baseline is missing |
| 64 | Invalid invocation or input; inspect stderr |

Do not use `check=True`, a bare `set -e`, or an `&&` chain that discards reports
with verdict exits 1–3. A successfully decoded FAIL event is not a crashed tool,
and an offline FAIL does not establish the current machine's health.

```python
import json
import subprocess


def run_report(args: list[str], timeout: int = 30) -> dict:
    completed = subprocess.run(
        ["omnismi", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode not in {0, 1, 2, 3}:
        raise RuntimeError(completed.stderr.strip())
    return json.loads(completed.stdout)


report = run_report([
    "decode", "--vendor", "nvidia", "--namespace", "xid", "--code", "48"
])
print(report["status"])
print(report["data"]["findings"])
```

The overview, `doctor`, `validate-spec`, and legacy `bench bandwidth` commands
use `-o json` for automation and retain their older process-exit behavior. Their
reports use `apiVersion`/`kind` and a `summary`; do not assume they have the same
schema as the `schema_version`/`report_type` family above. Always inspect the
report's status fields rather than treating process exit 0 as device health.

## Preserve evidence and limitations

- Keep stdout for every verdict exit from 0 through 3.
- Read `status`, `scope`, `evidence`, and `limitations`; missing evidence is not
  proof that hardware is healthy.
- Preserve `null` metrics as unavailable values rather than replacing them with
  zero or inventing measurements.
- Keep vendor sources attached to decoded findings when presenting conclusions.
- Apply an outer subprocess timeout in addition to the command's collector or
  workload deadline when an agent framework can cancel stuck operations.
- Save generated reports to an explicit artifact path when another tool or a
  human will review them later.

See [CLI](cli.md) for the complete command map, [Diagnostics](v2/diagnostics.md)
for evidence semantics, and [Compatibility](compatibility.md) for the difference
between an implemented adapter and a validated hardware model.
