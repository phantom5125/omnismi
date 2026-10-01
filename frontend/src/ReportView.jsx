import React, { useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Info,
  Terminal,
} from "lucide-react";
import { operators, reasons, reasonFor, summarize } from "./report.js";
import { Definition, Status } from "./ui.jsx";

function Inspector({ row, siblings, select, onRetest }) {
  const { case: test, failure, record, status } = row;
  return (
    <aside className="panel inspector" aria-label="Case details">
      <div className="section-heading">
        <h2>{status === "FAIL" ? "Mismatch details" : "Case details"}</h2>
        <Status status={status} />
      </div>
      <select
        className="case-selector"
        aria-label="Select case"
        value={test.id}
        onChange={(e) => select(e.target.value)}
      >
        {siblings.map((s) => (
          <option key={s.case.id} value={s.case.id}>
            {s.case.id}
          </option>
        ))}
      </select>
      <Definition
        items={[
          ["dtype", test.dtype],
          ["shape", test.shape.join(" × ")],
          ...(test.operator === "topk" ? [["k", test.k]] : []),
          ["seed", failure?.seed ?? record?.last_seed],
          ["Details", reasonFor(row)],
        ]}
      />
      <details className="technical">
        <summary>Technical details</summary>
        <Definition
          items={[
            ["Layout", test.layout],
            ["Input pattern", test.pattern],
            ["largest", test.largest],
            ["sorted", test.sorted],
            ["Comparisons", record?.comparisons ?? 0],
            ["Comparison", record?.last_comparison?.comparison],
            ["Relative tolerance", record?.last_comparison?.rtol ?? 0],
            ["Absolute tolerance", record?.last_comparison?.atol ?? 0],
            [
              "Mismatch locations",
              failure?.examples ? JSON.stringify(failure.examples) : null,
            ],
            ["Evidence file", failure?.artifact],
            ["Runtime details", record?.detail],
          ]}
        />
      </details>
      <section className="next-steps">
        <h2>Next steps</h2>
        <ol>
          {(status === "FAIL"
            ? [
                "Save the report and evidence.",
                "Repeat on the same device.",
                "Compare another device or runtime version.",
              ]
            : status === "PASS"
              ? [
                  "Save this report.",
                  "Try more cases or repetitions.",
                  "Review what remains untested.",
                ]
              : [
                  "Check the runtime and device.",
                  "Review limits and incomplete checks.",
                  "Run again and import the new report.",
                ]
          ).map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        <button className="button outline full" onClick={onRetest}>
          <Terminal size={17} />
          Prepare a retest
        </button>
      </section>
    </aside>
  );
}

function PowerEvidence({ telemetry }) {
  if (!telemetry) return null;
  const samples = telemetry.samples;
  const peak = Math.max(0, ...samples.map((s) => s.power_w));
  const maximum = Math.max(1, peak);
  const points = samples
    .filter((_, i) => i % Math.max(1, Math.ceil(samples.length / 200)) === 0)
    .map(
      (s, i, values) =>
        `${(i / Math.max(1, values.length - 1)) * 800},${90 - (s.power_w / maximum) * 80}`,
    )
    .join(" ");
  return (
    <section className="panel power">
      <div className="section-heading">
        <h2>Power observations</h2>
        <span className="muted">
          {samples.length
            ? `${samples.length} samples · Peak ${peak.toFixed(1)} W`
            : "No device-attributed samples"}
        </span>
      </div>
      {samples.length ? (
        <svg
          className="power-chart"
          viewBox="0 0 800 100"
          role="img"
          aria-label={`Power samples, peak ${peak.toFixed(1)} watts`}
        >
          <line x1="0" y1="90" x2="800" y2="90" stroke="var(--line)" />
          <polyline
            points={points}
            fill="none"
            stroke="var(--accent)"
            strokeWidth="2"
          />
        </svg>
      ) : null}
      <p className="muted">
        {telemetry.target_w == null
          ? "No power target was set. High-power behavior is unverified."
          : `Target ${telemetry.target_w} W · ${telemetry.target_observed ? "sampling criterion met" : "sampling criterion not met"}`}{" "}
        Samples are shown in order. Brief power spikes may be missed.
      </p>
    </section>
  );
}

export default function ReportView({ report, onRetest, onHardware }) {
  const summary = summarize(report);
  const { rows, counts, status } = summary;
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState(
    () => rows.find((r) => r.status === "FAIL")?.case.id || rows[0].case.id,
  );
  const current = rows.find((r) => r.case.id === selected) || rows[0];
  const grouped = Object.keys(operators)
    .map((op) => {
      const members = rows.filter((r) => r.case.operator === op);
      return (
        members.find((r) => r.status === "FAIL") ||
        members.find((r) => r.status === "INCONCLUSIVE") ||
        members.find((r) => r.status === "NOT_RUN") ||
        members[0]
      );
    })
    .filter(Boolean);
  const visible =
    filter === "all"
      ? grouped
      : rows.filter((r) =>
          filter === "fail"
            ? r.status === "FAIL"
            : ["NOT_RUN", "INCONCLUSIVE"].includes(r.status),
        );
  function changeFilter(value) {
    setFilter(value);
    const first = rows.find(
      (r) =>
        value === "all" ||
        (value === "fail"
          ? r.status === "FAIL"
          : ["NOT_RUN", "INCONCLUSIVE"].includes(r.status)),
    );
    if (first) setSelected(first.case.id);
  }
  const title =
    status === "FAIL"
      ? "Numerical mismatch found"
      : status === "PASS"
        ? "Selected checks passed"
        : !report.executed
          ? "Test plan · Not run yet"
          : "More evidence needed";
  const firstFailure = rows.find((r) => r.status === "FAIL");
  const explanation =
    status === "FAIL"
      ? `${firstFailure?.case.operator || "Operator"} returned an unexpected result. Retest before drawing conclusions about the hardware.`
      : status === "PASS"
        ? "The selected checks met their criteria. This does not certify the entire device."
        : !report.executed
          ? "Review the scope, then run the test on your device."
          : (Object.hasOwn(reasons, report.errors?.[0]?.reason)
              ? reasons[report.errors[0].reason]
              : null) ||
            "Some checks or acceptance criteria are incomplete. Review the details below.";
  return (
    <>
      <section className="device-heading">
        <h1>
          {report.identity?.name ||
            report.target?.name ||
            "Device not identified"}
        </h1>
        <p>
          {
            { smoke: "Quick", extended: "Extended", soak: "Load" }[
              report.config.profile
            ]
          }{" "}
          ·{" "}
          {report.config.vendor === "google"
            ? "JAX / TPU"
            : report.config.vendor === "amd"
              ? "ROCm / PyTorch"
              : report.config.vendor === "nvidia"
                ? "CUDA / PyTorch"
                : report.config.vendor}{" "}
          · One visible device
        </p>
      </section>
      <section
        className={`verdict verdict-${status}`}
        aria-label="Test conclusion"
      >
        {status === "PASS" ? (
          <CheckCircle2 size={36} />
        ) : (
          <AlertTriangle size={36} />
        )}
        <div>
          <h2>{title}</h2>
          <p>{explanation}</p>
        </div>
        {firstFailure ? (
          <button
            className="text-button"
            onClick={() => {
              setFilter("fail");
              setSelected(firstFailure.case.id);
            }}
          >
            View mismatch <ArrowRight size={18} />
          </button>
        ) : null}
      </section>
      <section className="metrics" aria-label="Case summary">
        <div>
          <strong className="positive">{counts.PASS}</strong>
          <span>Passed</span>
        </div>
        <div>
          <strong className="negative">{counts.FAIL}</strong>
          <span>Mismatch</span>
        </div>
        <div>
          <strong className="caution">
            {counts.NOT_RUN + counts.INCONCLUSIVE}
          </strong>
          <span>{counts.INCONCLUSIVE ? "Incomplete" : "Not run"}</span>
        </div>
        <div>
          <strong className="unknown">Unknown</strong>
          <span>Physical coverage</span>
        </div>
      </section>
      <div className="results-layout">
        <section className="panel checks">
          <h2>Operator checks</h2>
          <div className="tabs" role="group" aria-label="Filter test results">
            {[
              ["all", `All (${rows.length})`],
              ["fail", `Mismatches (${counts.FAIL})`],
              [
                "pending",
                `Incomplete (${counts.NOT_RUN + counts.INCONCLUSIVE})`,
              ],
            ].map(([value, label]) => (
              <button
                key={value}
                aria-pressed={filter === value}
                onClick={() => changeFilter(value)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Check</th>
                  <th>Result</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr
                    key={row.case.id}
                    className={
                      row.case.id === selected ||
                      (filter === "all" &&
                        row.case.operator === current.case.operator)
                        ? `selected selected-${current.status}`
                        : ""
                    }
                  >
                    <td>
                      <button
                        className="row-button"
                        onClick={() => setSelected(row.case.id)}
                        aria-pressed={row.case.id === selected}
                      >
                        {operators[row.case.operator]}{" "}
                        <code>
                          {filter === "all" ? row.case.operator : row.case.id}
                        </code>
                      </button>
                    </td>
                    <td>
                      <Status status={row.status} />
                    </td>
                    <td>
                      {reasonFor(row).replace(
                        "Returned values do not match the input at their indices.",
                        "Value/index mismatch",
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!visible.length ? (
              <p className="no-rows">No cases in this view.</p>
            ) : null}
          </div>
          <p className="table-note">
            <Info size={17} />
            Grouped by operator. Select a row to inspect its cases.
          </p>
        </section>
        <Inspector
          row={current}
          siblings={rows.filter(
            (r) => r.case.operator === current.case.operator,
          )}
          select={setSelected}
          onRetest={onRetest}
        />
      </div>
      <div className="scope-strip">
        Test scope{" "}
        <span>
          Attempted {summary.attempted} / {rows.length}
        </span>
        <span>XID/RAS not collected</span>
        <span>Device health unknown</span>
        <button className="text-button" onClick={onHardware}>
          Explore hardware <ArrowRight size={15} />
        </button>
      </div>
      <PowerEvidence telemetry={report.telemetry} />
      <details className="report-details">
        <summary>Device and report details</summary>
        <Definition
          items={[
            ["Tool version", report.tool_version],
            ["Device UUID", report.identity?.uuid],
            ["Runtime device", report.identity?.execution_device],
            ["Framework version", report.identity?.framework_version],
            ["Runtime version", report.identity?.runtime_version],
            ["Report status", report.status],
            ["Run completed", report.complete],
          ]}
        />
        <pre>
          {JSON.stringify(
            {
              errors: report.errors || [],
              acceptance_gates: report.acceptance_gates || {},
              limitations: report.limitations || [],
            },
            null,
            2,
          )}
        </pre>
      </details>
    </>
  );
}
