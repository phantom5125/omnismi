export const MAX_REPORT_BYTES = 8 * 1024 * 1024;
export const operators = {
  topk: "Top-k selection",
  sort: "Sort",
  matmul: "Matrix multiply",
  copy: "Copy",
  add: "Add",
  mul: "Multiply",
  sum: "Sum",
  gather: "Gather",
};
export const reasons = {
  value_index_disagreement:
    "Returned values do not match the input at their indices.",
  cpu_reference_mismatch:
    "Values differ from the CPU reference beyond the allowed tolerance.",
  duplicate_indices: "A row contains duplicate indices.",
  index_out_of_bounds: "An index is outside the input range.",
  nonfinite_output: "Finite inputs produced unexpected NaN or infinity.",
  output_shape_mismatch: "The output shape is incorrect.",
  missing_indices: "No indices were returned for comparison.",
  execution_error:
    "Execution failed. Check runtime support and available memory.",
  tensor_budget_exceeded: "This case exceeds the tensor memory budget.",
  runtime_unavailable: "No supported runtime or device was found.",
  target_device_mismatch:
    "The device does not match the selected model. No tests ran.",
  worker_timeout: "Time limit reached. Earlier results were preserved.",
  deadline_exceeded: "Time limit reached. Some checks are incomplete.",
  worker_error: "The worker stopped. Check the runtime details in the report.",
  worker_incomplete:
    "The run is incomplete. Check the runtime and time budget.",
};
const object = (value) =>
  value && typeof value === "object" && !Array.isArray(value);
const verdicts = ["PASS", "FAIL", "INCONCLUSIVE"];
const vendors = ["nvidia", "amd", "google", "cambricon", "alibaba"];
const boundedText = (value, length = 512) =>
  typeof value === "string" && value.length <= length;
const integer = (value, min, max) =>
  Number.isInteger(value) && value >= min && value <= max;

export function validateReport(report) {
  if (
    !object(report) ||
    report.schema_version !== 1 ||
    report.report_type !== "hardware_selftest"
  ) {
    throw new Error(
      "Choose an Omnismi self-test JSON report with schema_version=1.",
    );
  }
  if (
    !verdicts.includes(report.status) ||
    !object(report.config) ||
    !vendors.includes(report.config.vendor) ||
    !["smoke", "extended", "soak"].includes(report.config.profile) ||
    !integer(report.config.passes, 1, 100) ||
    typeof report.executed !== "boolean" ||
    typeof report.complete !== "boolean"
  ) {
    throw new Error(
      "The report is missing a valid status or test configuration.",
    );
  }
  if (
    !Array.isArray(report.cases) ||
    report.cases.length > 10000 ||
    !report.cases.length
  ) {
    throw new Error("A report must contain 1–10,000 planned cases.");
  }
  function checkCase(item) {
    if (
      !object(item) ||
      !boundedText(item.id, 100) ||
      !item.id ||
      !boundedText(item.operator, 20) ||
      !Object.hasOwn(operators, item.operator) ||
      !Array.isArray(item.shape) ||
      item.shape.length !== 2 ||
      !item.shape.every((n) => integer(n, 1, 10000000)) ||
      !["float32", "float16", "bfloat16", "int32"].includes(item.dtype)
    ) {
      throw new Error("A test case has an invalid format.");
    }
  }
  report.cases.forEach(checkCase);
  const plannedCases = new Map(report.cases.map((item) => [item.id, item]));
  const ids = new Set(plannedCases.keys());
  if (ids.size !== report.cases.length)
    throw new Error("The plan contains duplicate case IDs.");
  const resultIds = new Set();
  for (const key of ["results", "failures", "errors"]) {
    if (
      report[key] !== undefined &&
      (!Array.isArray(report[key]) || report[key].length > 10000)
    ) {
      throw new Error(`Invalid report field: ${key}.`);
    }
  }
  for (const item of report.results || []) {
    if (!object(item)) throw new Error("Invalid case result.");
    checkCase(item.case);
    if (
      resultIds.has(item.case.id) ||
      !verdicts.includes(item.status) ||
      !integer(item.executions, 0, 1e9) ||
      !integer(item.comparisons, 0, item.executions)
    ) {
      throw new Error(
        "The report contains duplicate IDs or inconsistent result counts.",
      );
    }
    if (!ids.has(item.case.id) && item.case.id !== "9000-matmul-load") {
      throw new Error("A result does not belong to this test plan.");
    }
    const planned = plannedCases.get(item.case.id);
    if (
      planned &&
      [
        "operator",
        "dtype",
        "shape",
        "k",
        "layout",
        "largest",
        "sorted",
        "pattern",
      ].some(
        (key) =>
          JSON.stringify(planned[key]) !== JSON.stringify(item.case[key]),
      )
    ) {
      throw new Error("Result parameters do not match the planned case.");
    }
    resultIds.add(item.case.id);
  }
  for (const failure of report.failures || []) {
    if (!object(failure)) throw new Error("Invalid failure record.");
    checkCase(failure.case);
    if (!ids.has(failure.case.id) && !resultIds.has(failure.case.id))
      throw new Error("A failure does not belong to this test plan.");
  }
  for (const error of report.errors || []) {
    if (!object(error)) throw new Error("Invalid error record.");
  }
  if (
    report.target !== undefined &&
    (!object(report.target) || !boundedText(report.target.name))
  )
    throw new Error("Invalid target model information.");
  if (
    report.synthetic_demo !== undefined &&
    typeof report.synthetic_demo !== "boolean"
  )
    throw new Error("Invalid demo marker.");
  if (report.acceptance_gates !== undefined && !object(report.acceptance_gates))
    throw new Error("Invalid acceptance criteria.");
  if (
    report.identity !== undefined &&
    (!object(report.identity) ||
      (report.identity.name !== undefined &&
        !boundedText(report.identity.name)))
  ) {
    throw new Error("Invalid device information.");
  }
  if (
    report.telemetry !== undefined &&
    (!object(report.telemetry) ||
      !Array.isArray(report.telemetry.samples) ||
      report.telemetry.samples.length > 7200 ||
      report.telemetry.samples.some(
        (s) =>
          !object(s) ||
          !Number.isFinite(s.power_w) ||
          s.power_w < 0 ||
          !Number.isFinite(s.timestamp_ns) ||
          !boundedText(s.phase, 30),
      ))
  ) {
    throw new Error("Invalid power samples.");
  }
  return report;
}

export function parseReport(text) {
  if (new TextEncoder().encode(text).length > MAX_REPORT_BYTES)
    throw new Error("Reports must be 8 MiB or smaller.");
  let report;
  try {
    report = JSON.parse(text);
  } catch {
    throw new Error(
      "Could not read JSON. Check that the file is complete and contains only the report.",
    );
  }
  return validateReport(report);
}

export function rowsFor(report) {
  const results = new Map((report.results || []).map((r) => [r.case.id, r]));
  const failures = new Map((report.failures || []).map((f) => [f.case.id, f]));
  const planned = [...report.cases];
  const load = results.get("9000-matmul-load");
  if (load && !planned.some((c) => c.id === load.case.id))
    planned.push(load.case);
  return planned.map((item) => {
    const record = results.get(item.id);
    const failure = failures.get(item.id);
    let status = "NOT_RUN";
    if (report.executed && (record || failure)) {
      status = failure || record?.status === "FAIL" ? "FAIL" : "INCONCLUSIVE";
      if (
        !failure &&
        record?.status === "PASS" &&
        record.comparisons >=
          (item.id === "9000-matmul-load" ? 1 : report.config.passes)
      )
        status = "PASS";
    }
    return { case: item, record, failure, status };
  });
}

export function summarize(report) {
  const rows = rowsFor(report);
  const counts = { PASS: 0, FAIL: 0, INCONCLUSIVE: 0, NOT_RUN: 0 };
  rows.forEach((row) => counts[row.status]++);
  let status = report.status;
  if (counts.FAIL || report.failures?.length) status = "FAIL";
  else if (
    !report.executed ||
    !report.complete ||
    counts.NOT_RUN ||
    counts.INCONCLUSIVE ||
    (report.errors || []).length ||
    (report.acceptance_gates &&
      Object.values(report.acceptance_gates).some((v) => v !== true))
  )
    status = "INCONCLUSIVE";
  return {
    rows,
    counts,
    status,
    attempted: rows.filter((r) => (r.record?.executions || 0) > 0).length,
  };
}

export function reasonFor(row) {
  if (row.status === "NOT_RUN") return "This case has not run.";
  const reason =
    row.failure?.reason ||
    row.record?.last_comparison?.reason ||
    row.record?.reason;
  return (
    (typeof reason === "string" && Object.hasOwn(reasons, reason)
      ? reasons[reason]
      : null) ||
    (row.status === "PASS"
      ? "Matches the CPU reference."
      : "Not enough evidence. Check the report details.")
  );
}

export function commandFor(config, targets, mode = "--run") {
  if (!["--run", "--plan"].includes(mode))
    throw new Error("Invalid execution mode.");
  if (
    !vendors.includes(config.vendor) ||
    !["smoke", "extended", "soak"].includes(config.profile)
  ) {
    throw new Error("Choose a supported vendor and test profile.");
  }
  const limits = {
    device: [0, 4095],
    seed: [0, 2 ** 32 - 1],
    passes: [1, 100],
    memory_mib: [16, 4096],
  };
  for (const [key, [min, max]] of Object.entries(limits)) {
    if (!integer(config[key], min, max))
      throw new Error(`${key} must be an integer from ${min} to ${max}.`);
  }
  for (const [key, maximum] of [
    ["timeout", 3600],
    ["duration", 1800],
  ]) {
    if (
      !Number.isFinite(config[key]) ||
      config[key] <= 0 ||
      config[key] > maximum
    )
      throw new Error(
        `${key} must be greater than 0 and at most ${maximum} seconds.`,
      );
  }
  const args = ["omnismi", "self-test", mode];
  if (config.target) {
    const target = targets.find((t) => t.id === config.target);
    if (!target || target.vendor !== config.vendor)
      throw new Error("The model and vendor do not match.");
    args.push("--target", target.id);
  } else args.push("--vendor", config.vendor);
  for (const key of [
    "device",
    "profile",
    "seed",
    "passes",
    "memory_mib",
    "timeout",
  ])
    args.push(`--${key.replaceAll("_", "-")}`, String(config[key]));
  if (config.profile === "soak")
    args.push("--duration", String(config.duration));
  if (config.operators) {
    if (
      !Array.isArray(config.operators) ||
      !config.operators.length ||
      config.operators.some(
        (op) => typeof op !== "string" || !Object.hasOwn(operators, op),
      ) ||
      new Set(config.operators).size !== config.operators.length ||
      (config.profile === "soak" && !config.operators.includes("matmul"))
    )
      throw new Error(
        "Choose valid, unique operators. Load tests require matmul.",
      );
    args.push("--operators", config.operators.join(","));
  }
  if (config.power_target_w != null) {
    if (
      config.profile !== "soak" ||
      !Number.isFinite(config.power_target_w) ||
      config.power_target_w <= 0
    )
      throw new Error(
        "A power target must be positive and requires the load profile.",
      );
    args.push("--power-target-w", String(config.power_target_w));
  }
  if (config.require_unit_coverage) args.push("--require-unit-coverage");
  // Never interpolate uploaded artifact paths or arbitrary report strings into a shell command.
  if (mode === "--run")
    args.push("--artifact-dir", "./sdc-evidence", ">", "selftest.json");
  return args.join(" ");
}

export function defaultConfig(target) {
  return {
    vendor: target.vendor,
    target: target.id,
    device: 0,
    profile: "smoke",
    seed: 20260930,
    passes: 1,
    memory_mib: 256,
    timeout: 120,
    duration: 60,
  };
}
