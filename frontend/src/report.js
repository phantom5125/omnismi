export const MAX_REPORT_BYTES = 8 * 1024 * 1024;
export const operators = {
  topk: "选择",
  sort: "排序",
  matmul: "矩阵乘法",
  copy: "数据拷贝",
  add: "加法",
  mul: "乘法",
  sum: "求和",
  gather: "索引读取",
};
export const reasons = {
  value_index_disagreement: "索引指向的输入值与返回值不一致。",
  cpu_reference_mismatch: "返回值超出 CPU 参考允许的误差范围。",
  duplicate_indices: "同一行返回了重复的索引。",
  index_out_of_bounds: "返回的索引超出输入范围。",
  nonfinite_output: "有限输入产生了非预期的 NaN 或无穷大。",
  output_shape_mismatch: "返回结果的形状不符合测试要求。",
  missing_indices: "没有返回可验证的索引。",
  execution_error: "执行未完成，可能缺少运行时、算子支持或可用内存。",
  tensor_budget_exceeded: "该用例超过本次设置的张量预算。",
  runtime_unavailable: "未找到可用的计算运行时或设备。",
  target_device_mismatch: "实际设备与选择的型号不匹配，未执行测试。",
  worker_timeout: "到达总时间预算，已保留此前观察到的结果。",
  deadline_exceeded: "到达总时间预算，部分检查未完成。",
  worker_error: "工作进程未能完成，请查看报告中的运行时信息。",
  worker_incomplete: "测试流程未完成，请检查运行时或增大预算。",
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
      "请选择 Omnismi self-test 生成的 schema_version=1 JSON 报告。",
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
    throw new Error("报告的状态、执行标记或设备配置不完整。");
  }
  if (
    !Array.isArray(report.cases) ||
    report.cases.length > 10000 ||
    !report.cases.length
  ) {
    throw new Error("报告需要包含 1–10000 个计划用例。");
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
      throw new Error("报告包含无法识别的用例结构。");
    }
  }
  report.cases.forEach(checkCase);
  const plannedCases = new Map(report.cases.map((item) => [item.id, item]));
  const ids = new Set(plannedCases.keys());
  if (ids.size !== report.cases.length)
    throw new Error("报告包含重复的计划用例 ID。");
  const resultIds = new Set();
  for (const key of ["results", "failures", "errors"]) {
    if (
      report[key] !== undefined &&
      (!Array.isArray(report[key]) || report[key].length > 10000)
    ) {
      throw new Error(`报告的 ${key} 字段格式不正确。`);
    }
  }
  for (const item of report.results || []) {
    if (!object(item)) throw new Error("无效的用例结果。");
    checkCase(item.case);
    if (
      resultIds.has(item.case.id) ||
      !verdicts.includes(item.status) ||
      !integer(item.executions, 0, 1e9) ||
      !integer(item.comparisons, 0, item.executions)
    ) {
      throw new Error("报告包含重复 ID、无效状态或不一致的比较次数。");
    }
    if (!ids.has(item.case.id) && item.case.id !== "9000-matmul-load") {
      throw new Error("执行结果与测试计划不匹配。");
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
      throw new Error("执行结果与计划中的算子参数不一致。");
    }
    resultIds.add(item.case.id);
  }
  for (const failure of report.failures || []) {
    if (!object(failure)) throw new Error("无效的失败记录。");
    checkCase(failure.case);
    if (!ids.has(failure.case.id) && !resultIds.has(failure.case.id))
      throw new Error("失败记录与测试计划不匹配。");
  }
  for (const error of report.errors || []) {
    if (!object(error)) throw new Error("无效的错误记录。");
  }
  if (
    report.target !== undefined &&
    (!object(report.target) || !boundedText(report.target.name))
  )
    throw new Error("目标型号信息格式不正确。");
  if (
    report.synthetic_demo !== undefined &&
    typeof report.synthetic_demo !== "boolean"
  )
    throw new Error("演示标记格式不正确。");
  if (report.acceptance_gates !== undefined && !object(report.acceptance_gates))
    throw new Error("验收条件格式不正确。");
  if (
    report.identity !== undefined &&
    (!object(report.identity) ||
      (report.identity.name !== undefined &&
        !boundedText(report.identity.name)))
  ) {
    throw new Error("设备身份信息格式不正确。");
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
    throw new Error("功率采样数据格式不正确。");
  }
  return report;
}

export function parseReport(text) {
  if (new TextEncoder().encode(text).length > MAX_REPORT_BYTES)
    throw new Error("报告不能超过 8 MiB。");
  let report;
  try {
    report = JSON.parse(text);
  } catch {
    throw new Error("无法读取 JSON，请确认文件完整且不包含命令输出。");
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
  if (row.status === "NOT_RUN") return "此用例尚未执行，不计入通过。";
  const reason =
    row.failure?.reason ||
    row.record?.last_comparison?.reason ||
    row.record?.reason;
  return (
    (typeof reason === "string" && Object.hasOwn(reasons, reason)
      ? reasons[reason]
      : null) ||
    (row.status === "PASS" ? "与 CPU 参考一致。" : "证据不足，请查看原始报告。")
  );
}

export function commandFor(config, targets, mode = "--run") {
  if (!["--run", "--plan"].includes(mode)) throw new Error("无效的执行模式。");
  if (
    !vendors.includes(config.vendor) ||
    !["smoke", "extended", "soak"].includes(config.profile)
  ) {
    throw new Error("请选择支持的厂商和测试方案。");
  }
  const limits = {
    device: [0, 4095],
    seed: [0, 2 ** 32 - 1],
    passes: [1, 100],
    memory_mib: [16, 4096],
  };
  for (const [key, [min, max]] of Object.entries(limits)) {
    if (!integer(config[key], min, max))
      throw new Error(`${key} 必须是 ${min}–${max} 的整数。`);
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
      throw new Error(`${key} 必须大于 0 且不超过 ${maximum} 秒。`);
  }
  const args = ["omnismi", "self-test", mode];
  if (config.target) {
    const target = targets.find((t) => t.id === config.target);
    if (!target || target.vendor !== config.vendor)
      throw new Error("型号与厂商不匹配。");
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
      throw new Error("报告包含不支持的算子。");
    args.push("--operators", config.operators.join(","));
  }
  if (config.power_target_w != null) {
    if (
      config.profile !== "soak" ||
      !Number.isFinite(config.power_target_w) ||
      config.power_target_w <= 0
    )
      throw new Error("功率目标需要有效的 soak 配置。");
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
