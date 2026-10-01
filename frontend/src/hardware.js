import { summarize } from "./report.js";

// Attach evidence only to an explicitly selected and identified model. Architecture
// descriptions are static knowledge; a diagram is never a discovered unit inventory.
export function moduleEvidence(report, target, module) {
  const base = {
    physicalCoverage: "UNKNOWN",
    rows: [],
    synthetic: !!report?.synthetic_demo,
  };
  if (!report) return { ...base, state: "no_report" };
  if (
    report.config.target !== target.id ||
    report.config.vendor !== target.vendor
  )
    return { ...base, state: "different_target" };
  if (!report.executed) return { ...base, state: "plan" };
  if (
    report.errors?.some((error) => error.reason === "target_device_mismatch") ||
    report.identity?.vendor !== target.vendor ||
    !new RegExp(target.name_pattern, "i").test(report.identity?.name || "")
  )
    return { ...base, state: "unverified_identity" };
  if (!module.operators.length) return { ...base, state: "no_check" };
  return {
    ...base,
    state: "related_checks",
    rows: summarize(report).rows.filter((row) =>
      module.operators.includes(row.case.operator),
    ),
  };
}
