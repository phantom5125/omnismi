import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";
import { demoReport } from "./demo.js";
import {
  parseReport,
  summarize,
  reasonFor,
  commandFor,
  defaultConfig,
} from "./report.js";
const catalog = JSON.parse(
  readFileSync(
    new URL("../../src/omnismi/selftest/targets.json", import.meta.url),
  ),
);
const roundtrip = (report) => parseReport(JSON.stringify(report));

test("synthetic evidence stays labelled, and sort cannot hide topk failure", () => {
  const report = roundtrip(demoReport());
  assert.equal(report.synthetic_demo, true);
  const summary = summarize(report);
  assert.deepEqual(summary.counts, {
    PASS: 7,
    FAIL: 1,
    NOT_RUN: 5,
    INCONCLUSIVE: 0,
  });
  assert.equal(summary.status, "FAIL");
  assert.equal(summary.attempted, 8);
  assert.equal(
    summary.rows.find((r) => r.case.operator === "sort").status,
    "PASS",
  );
});

test("an unexecuted plan or partial comparisons cannot become PASS", () => {
  const report = demoReport();
  report.status = "PASS";
  report.failures = [];
  report.results = [];
  report.executed = false;
  assert.equal(summarize(roundtrip(report)).status, "INCONCLUSIVE");
  assert.equal(summarize(report).counts.NOT_RUN, 13);
  report.executed = report.complete = true;
  report.results = report.cases.map((c) => ({
    case: c,
    status: "PASS",
    executions: 1,
    comparisons: 1,
  }));
  assert.equal(summarize(report).status, "PASS");
  report.config.passes = 2;
  assert.equal(summarize(report).counts.INCONCLUSIVE, 13);
  report.config.passes = 1;
  report.acceptance_gates = { power_target: false };
  assert.equal(summarize(report).status, "INCONCLUSIVE");
});

test("raw PASS cannot mask a failure, runtime error, or missing case", () => {
  const report = demoReport();
  report.status = "PASS";
  assert.equal(summarize(report).status, "FAIL");
  report.failures = [];
  report.results = report.results.filter((r) => r.status !== "FAIL");
  report.complete = true;
  assert.equal(summarize(report).status, "INCONCLUSIVE");
});

for (const [label, mutate] of [
  ["unknown schema", (r) => (r.schema_version = 2)],
  ["object profile", (r) => (r.config.profile = {})],
  ["object name", (r) => (r.target = { name: {} })],
  ["duplicate plan", (r) => r.cases.push(r.cases[0])],
  ["duplicate result", (r) => r.results.push(r.results[0])],
  [
    "mismatched parameters",
    (r) => (r.results[0].case = { ...r.results[0].case, dtype: "int32" }),
  ],
  ["impossible comparisons", (r) => (r.results[0].comparisons = 100)],
  [
    "unknown failure",
    (r) => (r.failures[0].case = { ...r.failures[0].case, id: "bogus" }),
  ],
  ["invalid telemetry", (r) => (r.telemetry = { samples: [{ power_w: -1 }] })],
])
  test(`reject ${label} without rendering untrusted structures`, () => {
    const r = structuredClone(demoReport());
    mutate(r);
    assert.throws(() => roundtrip(r));
  });

test("invalid JSON and oversized reports produce readable errors", () => {
  assert.throws(() => parseReport("nope"), /JSON/);
  assert.throws(() => parseReport(" ".repeat(8 * 1024 * 1024 + 1)), /8 MiB/);
  assert.equal(
    typeof reasonFor({
      status: "INCONCLUSIVE",
      record: { reason: "__proto__" },
    }),
    "string",
  );
});

test("commands use only validated arguments, never uploaded paths", () => {
  for (const target of catalog.targets) {
    const config = defaultConfig(target);
    config.artifact_dir = "$(touch /tmp/unsafe);bad";
    const command = commandFor(config, catalog.targets);
    assert.ok(command.includes(`--target ${target.id}`));
    assert.ok(
      command.endsWith("--artifact-dir ./sdc-evidence > selftest.json"),
    );
    assert.ok(!command.includes("unsafe"));
    assert.ok(
      !commandFor(config, catalog.targets, "--plan").includes("--artifact-dir"),
    );
  }
  const config = defaultConfig(catalog.targets[0]);
  for (const change of [
    { device: "0;bad" },
    { target: "bad" },
    { vendor: "amd" },
    { operators: ["copy;bad"] },
    { operators: ["copy", "copy"] },
    { profile: "soak", operators: ["topk"] },
    { power_target_w: 400 },
  ])
    assert.throws(() => commandFor({ ...config, ...change }, catalog.targets));
});

test("nonzero power evidence and load case remain additional observations", () => {
  const r = demoReport();
  r.telemetry = {
    samples: [{ power_w: 300, timestamp_ns: 123, phase: "load" }],
  };
  r.results.push({
    case: { ...r.cases[0], id: "9000-matmul-load", operator: "matmul" },
    status: "PASS",
    executions: 2,
    comparisons: 2,
  });
  assert.equal(summarize(roundtrip(r)).rows.length, 14);
  assert.equal(summarize(r).status, "FAIL");
});

test("load comparison count and fractional time budgets match the CLI", () => {
  const r = demoReport();
  r.config.passes = 3;
  r.results.push({
    case: { ...r.cases[0], id: "9000-matmul-load", operator: "matmul" },
    status: "PASS",
    executions: 1,
    comparisons: 1,
  });
  assert.equal(summarize(roundtrip(r)).rows.at(-1).status, "PASS");
  const c = {
    ...defaultConfig(catalog.targets[3]),
    profile: "soak",
    timeout: 90.5,
    duration: 1.25,
    power_target_w: 100.5,
  };
  const command = commandFor(c, catalog.targets);
  assert.ok(
    command.includes("--timeout 90.5 --duration 1.25 --power-target-w 100.5"),
  );
  assert.throws(() => commandFor({ ...c, timeout: NaN }, catalog.targets));
});
