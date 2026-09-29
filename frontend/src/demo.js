// Synthetic evidence, intentionally opt-in and labelled everywhere it is displayed.
export function demoReport() {
  const ops = ["copy", "add", "mul", "sum", "gather", "sort", "matmul"];
  const cases = ops.map((operator, index) => ({
    id: `${String(index).padStart(4, "0")}-${operator}`,
    operator,
    shape: operator === "matmul" ? [64, 64] : [7, 257],
    dtype: "float32",
    pattern: "random",
    layout: "contiguous",
    k: 1,
    largest: true,
    sorted: true,
  }));
  for (let n = 0; n < 6; n++)
    cases.push({
      ...cases[0],
      id: `${String(n + 7).padStart(4, "0")}-topk`,
      operator: "topk",
      k: n ? 7 : 1,
    });
  const results = cases
    .slice(0, 8)
    .map((test, i) => ({
      case: test,
      status: i === 7 ? "FAIL" : "PASS",
      executions: 1,
      comparisons: 1,
      last_seed: 20260930 + i * 1009,
      last_iteration: 0,
      phases: ["baseline"],
      last_comparison: {
        status: i === 7 ? "FAIL" : "PASS",
        comparison: "exact",
      },
    }));
  return {
    schema_version: 1,
    report_type: "hardware_selftest",
    tool_version: "2.1.0.dev0",
    status: "FAIL",
    executed: true,
    complete: false,
    phase: "finished",
    synthetic_demo: true,
    config: {
      vendor: "nvidia",
      target: "rtx-5090",
      device: 0,
      profile: "smoke",
      seed: 20260930,
      passes: 1,
      memory_mib: 256,
      timeout: 120,
      duration: 60,
    },
    identity: {
      vendor: "nvidia",
      name: "NVIDIA GeForce RTX 5090",
      framework: "pytorch",
      framework_version: "演示",
      execution_device: "cuda:0",
      uuid: null,
    },
    coverage: {
      planned_cases: 13,
      completed_cases: 7,
      comparison_count: 8,
      physical_units: {
        status: "UNKNOWN",
        observed_ids: [],
        expected_count: null,
      },
    },
    hardware_fault_confirmed: false,
    current_hardware_health: "INCONCLUSIVE",
    cases,
    results,
    errors: [],
    failures: [
      {
        case: cases[7],
        seed: 20267993,
        iteration: 0,
        phase: "baseline",
        status: "FAIL",
        reason: "value_index_disagreement",
        mismatch_count: 1,
        examples: [[0, 0]],
        classification: "numerical_mismatch_candidate_sdc",
        hardware_fault_confirmed: false,
      },
    ],
    limitations: ["合成故障演示，不代表任何真实硬件结果。"],
  };
}
