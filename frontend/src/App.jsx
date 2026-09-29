import React, { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  CirclePlay,
  ClipboardList,
  Crosshair,
  Download,
  FileJson,
  Info,
  List,
  Upload,
  Wrench,
  X,
} from "lucide-react";
import ReportView from "./ReportView.jsx";
import SetupView from "./SetupView.jsx";
import { SupportView, GuideView } from "./SupportView.jsx";
import { demoReport } from "./demo.js";
import { MAX_REPORT_BYTES, defaultConfig, parseReport } from "./report.js";

const navigation = [
  ["report", "测试报告", ClipboardList],
  ["setup", "开始自检", CirclePlay],
  ["support", "适配计划", List],
  ["guide", "阅读指南", BookOpen],
];

export default function App() {
  const [page, setPage] = useState("report");
  const [report, setReport] = useState(null);
  const [filename, setFilename] = useState("");
  const [error, setError] = useState("");
  const [initial, setInitial] = useState(null);
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
          showReport(value, "启动时载入的报告");
      })
      .catch((err) => {
        if (err.name !== "AbortError" && generation.current === baseline)
          setError(`启动报告未载入：${err.message}`);
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
      if (file.size > MAX_REPORT_BYTES) throw new Error("报告不能超过 8 MiB。");
      const value = parseReport(await file.text());
      if (generation.current === current) showReport(value, file.name);
    } catch (err) {
      if (generation.current === current) setError(err.message);
    }
  }
  function setup(config = null) {
    setInitial(config);
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
        跳转到主要内容
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
          <Crosshair size={29} />
          <span>Omnismi</span>
        </a>
        <nav aria-label="主导航">
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
            本地工具<small>数据留在本地浏览器</small>
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
                导出 JSON
              </button>
            ) : null}
            <button className="button primary" onClick={importAction}>
              <Upload size={17} />
              导入报告
            </button>
          </div>
        </header>
        <input
          ref={fileInput}
          className="sr-only"
          type="file"
          accept=".json,application/json"
          aria-label="导入自检 JSON 报告"
          onChange={(e) => {
            importFile(e.target.files[0]);
            e.target.value = "";
          }}
        />
        {error ? (
          <div className="error-notice" role="alert">
            <Info size={18} />
            {error}
            <button aria-label="关闭错误提示" onClick={() => setError("")}>
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
                    ? "演示数据 · 合成故障，用于说明界面，非真实设备结果。"
                    : `本地报告 · ${filename}`}
                </span>
                <button onClick={clearReport}>
                  {report.synthetic_demo ? "退出演示" : "移除报告"}
                </button>
              </div>
              <ReportView
                key={revision}
                report={report}
                onRetest={() =>
                  setup({
                    ...report.config,
                    duration: report.config.duration ?? 60,
                  })
                }
              />
            </>
          ) : (
            <section className="empty-state">
              <div className="empty-heading">
                <h1>看清每一次硬件测试</h1>
                <p>
                  导入报告，了解哪些检查通过、哪里有异常，以及下一步该做什么。
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
                <h2>还没有测试报告</h2>
                <p>拖入 selftest.json，或从本机选择文件。</p>
                <button className="button primary" onClick={importAction}>
                  <Upload size={17} />
                  选择 JSON 报告
                </button>
                <small>仅在本地解析 · 最大 8 MiB</small>
              </div>
              <div className="empty-actions">
                <button className="button" onClick={() => setup()}>
                  <CirclePlay size={18} />
                  第一次使用？生成测试命令
                </button>
                <button
                  className="text-button"
                  onClick={() => showReport(demoReport(), "合成演示")}
                >
                  查看演示报告
                </button>
              </div>
              <div className="onboarding">
                <div>
                  <span>01</span>
                  <h3>选择范围</h3>
                  <p>从快速检查开始，确认型号与设备编号。</p>
                </div>
                <div>
                  <span>02</span>
                  <h3>执行自检</h3>
                  <p>在目标机器运行，保留 JSON 和失败数据。</p>
                </div>
                <div>
                  <span>03</span>
                  <h3>理解结果</h3>
                  <p>先看结论，再检查用例与覆盖范围。</p>
                </div>
              </div>
            </section>
          )
        ) : null}
        {page === "setup" ? (
          <SetupView key={revision} initial={initial} onImport={importAction} />
        ) : null}
        {page === "support" ? (
          <SupportView onSelect={(target) => setup(defaultConfig(target))} />
        ) : null}
        {page === "guide" ? <GuideView onSetup={() => setup()} /> : null}
      </main>
    </div>
  );
}
