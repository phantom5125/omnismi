import React, { useRef, useState } from "react";
import {
  ArrowDownUp,
  ArrowRight,
  BookOpen,
  Cpu,
  ExternalLink,
  Info,
} from "lucide-react";
import catalog from "../../src/omnismi/selftest/hardware.json";
import targets from "../../src/omnismi/selftest/targets.json";
import { moduleEvidence } from "./hardware.js";
import { operators } from "./report.js";
import { Status } from "./ui.jsx";

const kinds = {
  operator_checks: "Related operator checks",
  dispatch_unverified: "Execution path unverified",
  no_dedicated_check: "No dedicated check",
};
const states = {
  no_report: "Import a report to see related checks here.",
  different_target: "The open report is for a different or unspecified target.",
  plan: "This report is a plan. No tests have run.",
  unverified_identity: "The report does not confirm this device model.",
  no_check: "This suite has no dedicated check for this module.",
};

function ModuleButton({ module, selected, onSelect }) {
  return (
    <button
      className={`hardware-block ${selected ? "is-selected" : ""}`}
      aria-pressed={selected}
      aria-controls="module-details"
      onClick={() => onSelect(module.id)}
    >
      <strong>{module.name}</strong>
      <span>{module.subtitle}</span>
      <small>
        {module.operators.length
          ? module.operators.join(" · ")
          : "No dedicated check"}
      </small>
    </button>
  );
}

export default function HardwareView({
  report,
  initialTarget,
  onSetup,
  onReport,
}) {
  const [targetId, setTarget] = useState(() =>
    targets.targets.some((t) => t.id === initialTarget)
      ? initialTarget
      : "rtx-5090",
  );
  const [moduleId, setModule] = useState("compute");
  const details = useRef(null);
  const diagram = useRef(null);
  function selectModule(id) {
    setModule(id);
    if (window.matchMedia("(max-width: 1180px)").matches) {
      details.current?.focus({ preventScroll: true });
      details.current?.scrollIntoView({ block: "start" });
    }
  }
  const target = targets.targets.find((t) => t.id === targetId);
  const profile = catalog.profiles.find((p) => p.id === targetId);
  const module =
    profile.modules.find((m) => m.id === moduleId) || profile.modules[0];
  const source = catalog.sources[module.source];
  const evidence = moduleEvidence(report, target, module);
  const priority = { FAIL: 0, INCONCLUSIVE: 1, NOT_RUN: 2, PASS: 3 };
  const previewRows = [...evidence.rows]
    .sort((a, b) => priority[a.status] - priority[b.status])
    .slice(0, 8);
  const showModule = (id) => {
    const item = profile.modules.find((m) => m.id === id);
    return item ? (
      <ModuleButton
        key={id}
        module={item}
        selected={module.id === id}
        onSelect={selectModule}
      />
    ) : null;
  };
  return (
    <section className="workflow-page hardware-page">
      <div className="hardware-heading">
        <div>
          <h1>Inside your accelerator</h1>
          <p className="lead">
            Select a module to see what it does, how we check it, and what
            remains unknown.
          </p>
        </div>
        <Cpu size={35} strokeWidth={1.3} aria-hidden="true" />
      </div>
      <div
        className="hardware-targets"
        role="group"
        aria-label="Choose hardware model"
      >
        {targets.targets.map((t) => (
          <button
            key={t.id}
            aria-pressed={targetId === t.id}
            onClick={() => {
              setTarget(t.id);
              setModule("compute");
            }}
          >
            <strong>{t.short_name}</strong>
            <span>{t.family}</span>
          </button>
        ))}
      </div>
      <div className="hardware-layout">
        <figure className="architecture" ref={diagram} tabIndex={-1}>
          <div className="architecture-heading">
            <div>
              <span className="eyebrow">ARCHITECTURE MAP</span>
              <h2>{target.name}</h2>
            </div>
            <span className="map-label">Conceptual</span>
          </div>
          <p className="map-instruction">Click any block to explore it.</p>
          <div className="compute-group">
            <span className="group-label">{profile.group}</span>
            <div className="compute-blocks">
              {["compute", "matrix", "local"].map(showModule)}
            </div>
          </div>
          <div className="data-path" aria-label="Logical data flow">
            <ArrowDownUp size={18} />
            <span>Data moves between compute and memory</span>
          </div>
          <div className="memory-blocks">
            {["cache", "memory"].map(showModule)}
          </div>
          <div className="module-rail">
            <span className="group-label">Connections & other engines</span>
            <div className="peripheral-blocks">
              {["host", "peer", "special"].map(showModule)}
            </div>
          </div>
          <figcaption>
            {profile.scope} Lines describe logical data flow, not measured
            traffic.
          </figcaption>
        </figure>
        <aside
          className="panel module-details"
          id="module-details"
          ref={details}
          tabIndex={-1}
          aria-label="Module details"
          aria-live="polite"
        >
          <span className="eyebrow">SELECTED MODULE</span>
          <h2>{module.name}</h2>
          <p className="module-purpose">{module.purpose}</p>
          <div className="module-coverage">
            <span>Physical coverage</span>
            <strong>Unknown</strong>
          </div>
          <h3>{kinds[module.evidence_kind]}</h3>
          {module.operators.length ? (
            <div className="operator-tags">
              {module.operators.map((op) => (
                <span key={op} title={operators[op]}>
                  {op}
                </span>
              ))}
            </div>
          ) : null}
          <p>{module.limitation}</p>
          <div className="module-evidence">
            <h3>
              {evidence.synthetic
                ? "Demo evidence · Synthetic"
                : "Report evidence"}
            </h3>
            {evidence.state === "related_checks" ? (
              <>
                <p>
                  Related results only. They do not establish this module’s
                  health.
                </p>
                {evidence.rows.length ? (
                  <ul>
                    {previewRows.map((row) => (
                      <li key={row.case.id}>
                        <code>{row.case.id}</code>
                        <Status status={row.status} />
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>No related cases in this report.</p>
                )}
                {evidence.rows.length > previewRows.length ? (
                  <p>
                    Showing {previewRows.length} of {evidence.rows.length}{" "}
                    related cases; mismatches first.
                  </p>
                ) : null}
                <button className="text-button" onClick={onReport}>
                  View test report <ArrowRight size={16} />
                </button>
              </>
            ) : (
              <p>{states[evidence.state]}</p>
            )}
          </div>
          <a
            className="source-link"
            href={source.url}
            target="_blank"
            rel="noreferrer"
          >
            <BookOpen size={17} />
            <span>
              {source.label}
              <small>{module.section}</small>
            </span>
            <ExternalLink size={14} />
          </a>
          <button
            className="text-button back-to-map"
            onClick={() => {
              diagram.current?.focus({ preventScroll: true });
              diagram.current?.scrollIntoView({ block: "start" });
            }}
          >
            Back to map
          </button>
        </aside>
      </div>
      <div className="map-note">
        <Info size={18} />
        <p>
          These maps explain the architecture. Operator-to-module links are
          Omnismi’s interpretation; the runtime chooses the actual execution
          path. A passing test does not prove every unit was used, and a
          mismatch does not locate a faulty module.
        </p>
      </div>
      <section className="hardware-readiness">
        <div>
          <h2>Test this model</h2>
          <p>
            <strong>{target.runtime}</strong> · Adapter implemented ·
            Real-device validation pending
          </p>
          <p>
            {target.requirements} {target.gaps}
          </p>
        </div>
        <button className="button primary" onClick={() => onSetup(target)}>
          Create test command <ArrowRight size={17} />
        </button>
      </section>
      <p className="catalog-note">
        Architecture sources reviewed {catalog.reviewed_at}. Selection reflects
        project priorities, not measured defect rates.{" "}
        <a
          href="https://github.com/phantom5125/omnismi"
          target="_blank"
          rel="noreferrer"
        >
          Contribute on GitHub <ExternalLink size={12} />
        </a>
      </p>
    </section>
  );
}
