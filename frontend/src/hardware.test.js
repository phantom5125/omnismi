import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { moduleEvidence } from "./hardware.js";
import { demoReport } from "./demo.js";
import { operators } from "./report.js";
const read = (file) =>
  JSON.parse(
    readFileSync(
      new URL(`../../src/omnismi/selftest/${file}.json`, import.meta.url),
    ),
  );
const { targets } = read("targets");
const catalog = read("hardware");
const rtx = targets[0];
const profile = catalog.profiles.find((p) => p.id === rtx.id);
const compute = profile.modules.find((m) => m.id === "compute");

test("every target has sourced modules with explicit limitations and known operators", () => {
  assert.deepEqual(
    catalog.profiles.map((p) => p.id).sort(),
    targets.map((t) => t.id).sort(),
  );
  for (const p of catalog.profiles) {
    assert.equal(new Set(p.modules.map((m) => m.id)).size, p.modules.length);
    for (const module of p.modules) {
      const source = catalog.sources[module.source];
      assert.ok(
        source && module.section && module.purpose && module.limitation,
      );
      assert.ok(
        [
          "developer.nvidia.com",
          "images.nvidia.com",
          "docs.nvidia.com",
          "resources.nvidia.com",
          "www.amd.com",
          "docs.cloud.google.com",
        ].includes(new URL(source.url).hostname),
      );
      assert.ok(module.operators.every((op) => Object.hasOwn(operators, op)));
    }
  }
  assert.equal(
    profile.modules.some((m) => m.id === "peer"),
    false,
    "RTX 5090 must not inherit B300 NVLink",
  );
  assert.equal(
    catalog.profiles
      .find((p) => p.id === "tpu-v6e")
      .modules.some((m) => m.name.includes("CUDA")),
    false,
  );
});

test("sort passing cannot erase a topk mismatch or label any physical unit failed", () => {
  const result = moduleEvidence(demoReport(), rtx, compute);
  assert.equal(result.state, "related_checks");
  assert.equal(result.synthetic, true);
  assert.equal(result.physicalCoverage, "UNKNOWN");
  assert.ok(
    result.rows.some((r) => r.case.operator === "sort" && r.status === "PASS"),
  );
  assert.ok(
    result.rows.some((r) => r.case.operator === "topk" && r.status === "FAIL"),
  );
  const matrix = profile.modules.find((m) => m.id === "matrix");
  assert.equal(matrix.evidence_kind, "dispatch_unverified");
  assert.equal(
    moduleEvidence(demoReport(), rtx, matrix).physicalCoverage,
    "UNKNOWN",
  );
});

test("evidence never leaks across models, ambiguous identities or unexecuted plans", () => {
  assert.equal(moduleEvidence(null, rtx, compute).state, "no_report");
  assert.equal(
    moduleEvidence(demoReport(), targets[1], compute).state,
    "different_target",
  );
  for (const [state, mutate] of [
    ["different_target", (r) => delete r.config.target],
    ["different_target", (r) => (r.config.vendor = "amd")],
    ["plan", (r) => (r.executed = false)],
    ["unverified_identity", (r) => delete r.identity],
    ["unverified_identity", (r) => (r.identity.name = "NVIDIA B300")],
    ["unverified_identity", (r) => (r.identity.vendor = "amd")],
    [
      "unverified_identity",
      (r) => r.errors.push({ reason: "target_device_mismatch" }),
    ],
  ]) {
    const report = demoReport();
    mutate(report);
    const result = moduleEvidence(report, rtx, compute);
    assert.equal(result.state, state);
    assert.equal(result.rows.length, 0);
    assert.equal(result.physicalCoverage, "UNKNOWN");
  }
  for (const module of profile.modules.filter((m) => !m.operators.length)) {
    const result = moduleEvidence(demoReport(), rtx, module);
    assert.equal(result.state, "no_check");
    assert.equal(result.rows.length, 0);
  }
});
