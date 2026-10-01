import React, { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  CirclePlay,
  ClipboardList,
  Download,
  FileJson,
  Info,
  List,
  Upload,
  Wrench,
  X,
} from "lucide-react";
import logoUrl from "../../docs/assets/OMNIsmi.svg";
import HardwareView from "./HardwareView.jsx";
import ReportView from "./ReportView.jsx";
import SetupView from "./SetupView.jsx";
import { GuideView } from "./GuideView.jsx";
import { demoReport } from "./demo.js";
import { MAX_REPORT_BYTES, defaultConfig, parseReport } from "./report.js";

const navigation = [
  ["report", "Test report", ClipboardList],
  ["setup", "Run a test", CirclePlay],
  ["hardware", "Hardware", List],
  ["guide", "Guide", BookOpen],
];

export default function App() {
  const [page, setPage] = useState("report");
  const [report, setReport] = useState(null);
  const [filename, setFilename] = useState("");
  const [error, setError] = useState("");
  const [initial, setInitial] = useState(null);
  const [retest, setRetest] = useState(false);
  const [revision, setRevision] = useState(0);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef(null);
  const generation = useRef(0);

  function showReport(value, name) {
    generation.current++;
    setReport(value);
    setFilename(name);
    setError("");
    setPage("report");
    setRevision((n) => n + 1);
  }
  useEffect(() => {
    const controller = new AbortController();
    const baseline = generation.current;
    fetch("/report.json", { signal: controller.signal })
      .then(async (response) => {
        if (
          !response.ok ||
          !response.headers.get("content-type")?.includes("application/json")
        )
          return;
        const text = await response.text();
        if (text.trim() === "null" || generation.current !== baseline) return;
        const value = parseReport(text);
        if (generation.current === baseline)
          showReport(value, "Preloaded report");
      })
      .catch((err) => {
        if (err.name !== "AbortError" && generation.current === baseline)
          setError(`Could not load the report: ${err.message}`);
      });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [page, revision]);
  async function importFile(file) {
    if (!file) return;
    const current = ++generation.current;
    setError("");
    try {
      if (file.size > MAX_REPORT_BYTES)
        throw new Error("Reports must be 8 MiB or smaller.");
      const value = parseReport(await file.text());
      if (generation.current === current) showReport(value, file.name);
    } catch (err) {
      if (generation.current === current) setError(err.message);
    }
  }
  function setup(config = null, isRetest = false) {
    setInitial(config);
    setRetest(isRetest);
    setRevision((n) => n + 1);
    setPage("setup");
  }
  function exportReport() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = report.synthetic_demo
      ? "omnismi-synthetic-demo.json"
      : "omnismi-selftest-report.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function clearReport() {
    generation.current++;
    setReport(null);
    setFilename("");
    setError("");
  }
  const importAction = () => fileInput.current?.click();
  return (
    <div className="app-shell">
      <a className="skip-link" href="#content">
        Skip to content
      </a>
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("report");
          }}
        >
          <img src={logoUrl} alt="Omnismi" width="311" height="111" />
        </a>
        <nav aria-label="Main navigation">
          {navigation.map(([key, label, Icon]) => (
            <button
              key={key}
              className={page === key ? "active" : ""}
              aria-current={page === key ? "page" : undefined}
              onClick={() => (key === "setup" ? setup() : setPage(key))}
            >
              <Icon size={22} />
              {label}
            </button>
          ))}
        </nav>
        <button className="local-note" onClick={() => setPage("guide")}>
          <Wrench size={20} />
          <span>
            Local workspace<small>Your reports stay here</small>
          </span>
        </button>
      </aside>
      <main id="content">
        <header className="topbar">
          <h2>{navigation.find(([key]) => key === page)[1]}</h2>
          <div className="header-actions">
            {report ? (
              <button className="button" onClick={exportReport}>
                <Download size={17} />
                Export JSON
              </button>
            ) : null}
            <button className="button primary" onClick={importAction}>
              <Upload size={17} />
              Import report
            </button>
          </div>
        </header>
        <input
          ref={fileInput}
          className="sr-only"
          type="file"
          accept=".json,application/json"
          aria-label="Import self-test JSON report"
          onChange={(e) => {
            importFile(e.target.files[0]);
            e.target.value = "";
          }}
        />
        {error ? (
          <div className="error-notice" role="alert">
            <Info size={18} />
            {error}
            <button aria-label="Dismiss error" onClick={() => setError("")}>
              <X size={17} />
            </button>
          </div>
        ) : null}
        {page === "report" ? (
          report ? (
            <>
              <div
                className={`report-banner ${report.synthetic_demo ? "demo-banner" : ""}`}
              >
                <Info size={19} />
                <span>
                  {report.synthetic_demo
                    ? "Demo · Synthetic results. No real hardware was tested."
                    : `Local report · ${filename}`}
                </span>
                <button onClick={clearReport}>
                  {report.synthetic_demo ? "Close demo" : "Remove report"}
                </button>
              </div>
              <ReportView
                key={revision}
                report={report}
                onHardware={() => setPage("hardware")}
                onRetest={() =>
                  setup(
                    {
                      ...report.config,
                      duration: report.config.duration ?? 60,
                    },
                    true,
                  )
                }
              />
            </>
          ) : (
            <section className="empty-state">
              <div className="empty-heading">
                <h1>Understand your hardware tests</h1>
                <p>
                  See what passed, what needs attention, and what to do next.
                </p>
              </div>
              <div
                className={`dropzone ${dragging ? "dragging" : ""}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  importFile(e.dataTransfer.files[0]);
                }}
              >
                <FileJson size={46} strokeWidth={1.4} />
                <h2>Open a test report</h2>
                <p>Drop selftest.json here, or choose a file.</p>
                <button className="button primary" onClick={importAction}>
                  <Upload size={17} />
                  Choose JSON file
                </button>
                <small>Local only · Up to 8 MiB</small>
              </div>
              <div className="empty-actions">
                <button className="button" onClick={() => setup()}>
                  <CirclePlay size={18} />
                  Create a test command
                </button>
                <button
                  className="text-button"
                  onClick={() => showReport(demoReport(), "Synthetic demo")}
                >
                  Explore a demo
                </button>
              </div>
              <div className="onboarding">
                <div>
                  <span>01</span>
                  <h3>Choose a test</h3>
                  <p>Start with a quick check on one device.</p>
                </div>
                <div>
                  <span>02</span>
                  <h3>Run the command</h3>
                  <p>Run on your test machine and save the report.</p>
                </div>
                <div>
                  <span>03</span>
                  <h3>Review the results</h3>
                  <p>Check the result, then explore the evidence.</p>
                </div>
              </div>
            </section>
          )
        ) : null}
        {page === "setup" ? (
          <SetupView
            key={revision}
            initial={initial}
            retest={retest}
            onImport={importAction}
          />
        ) : null}
        {page === "hardware" ? (
          <HardwareView
            report={report}
            initialTarget={report?.config.target}
            onSetup={(target) => setup(defaultConfig(target))}
            onReport={() => setPage("report")}
          />
        ) : null}
        {page === "guide" ? <GuideView onSetup={() => setup()} /> : null}
      </main>
    </div>
  );
}
