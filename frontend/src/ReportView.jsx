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
    <aside className="panel inspector" aria-label="用例详情">
      <div className="section-heading">
        <h2>{status === "FAIL" ? "异常详情" : "用例详情"}</h2>
        <Status status={status} />
      </div>
      <select
        className="case-selector"
        aria-label="选择用例"
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
          ["说明", reasonFor(row)],
        ]}
      />
      <details className="technical">
        <summary>更多技术参数</summary>
        <Definition
          items={[
            ["布局", test.layout],
            ["输入分布", test.pattern],
            ["largest", test.largest],
            ["sorted", test.sorted],
            ["比较次数", record?.comparisons ?? 0],
            ["比较方式", record?.last_comparison?.comparison],
            ["相对容差", record?.last_comparison?.rtol ?? 0],
            ["绝对容差", record?.last_comparison?.atol ?? 0],
            [
              "失败坐标",
              failure?.examples ? JSON.stringify(failure.examples) : null,
            ],
            ["失败数据文件", failure?.artifact],
            ["运行时详情", record?.detail],
          ]}
        />
      </details>
      <section className="next-steps">
        <h2>下一步</h2>
        <ol>
          {(status === "FAIL"
            ? ["保存报告与失败数据", "同卡重复测试", "换卡或更换框架版本对照"]
            : status === "PASS"
              ? [
                  "保存本次测试报告",
                  "扩大用例或增加重复次数",
                  "结合覆盖范围判断下一步",
                ]
              : [
                  "确认运行时与设备可用",
                  "查看预算和未完成原因",
                  "执行检查后重新导入报告",
                ]
          ).map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        <button className="button outline full" onClick={onRetest}>
          <Terminal size={17} />
          生成复测命令
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
        <h2>功率证据</h2>
        <span className="muted">
          {samples.length
            ? `${samples.length} 个样本 · 峰值 ${peak.toFixed(1)} W`
            : "未取得可归属的采样"}
        </span>
      </div>
      {samples.length ? (
        <svg
          className="power-chart"
          viewBox="0 0 800 100"
          role="img"
          aria-label={`功率采样曲线，峰值 ${peak.toFixed(1)} 瓦`}
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
          ? "本次未设置功率目标，不能据此宣称通过高功率验证。"
          : `目标 ${telemetry.target_w} W · ${telemetry.target_observed ? "报告记录达到采样条件" : "尚未满足采样条件"}`}{" "}
        曲线按采样顺序排列。软件采样无法捕捉所有瞬态尖峰。
      </p>
    </section>
  );
}

export default function ReportView({ report, onRetest }) {
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
      ? "发现数值异常"
      : status === "PASS"
        ? "所选检查通过"
        : !report.executed
          ? "这是一份测试计划"
          : "还不能得出结论";
  const firstFailure = rows.find((r) => r.status === "FAIL");
  const explanation =
    status === "FAIL"
      ? `${firstFailure?.case.operator || "算子"} 的结果与 CPU 参考或算子要求不一致。需要复测，尚不能确认硬件故障。`
      : status === "PASS"
        ? "本次已执行的检查符合预期。通过仅覆盖所选用例，不代表整卡健康。"
        : !report.executed
          ? "尚未执行计算。先确认测试范围，再在目标机器运行自检。"
          : (Object.hasOwn(reasons, report.errors?.[0]?.reason)
              ? reasons[report.errors[0].reason]
              : null) ||
            "部分检查或验收条件尚未满足。请查看未完成的用例与覆盖范围。";
  return (
    <>
      <section className="device-heading">
        <h1>
          {report.identity?.name || report.target?.name || "尚未识别设备"}
        </h1>
        <p>
          {report.config.profile} ·{" "}
          {report.config.vendor === "google"
            ? "JAX / TPU"
            : report.config.vendor === "amd"
              ? "ROCm / PyTorch"
              : report.config.vendor === "nvidia"
                ? "CUDA / PyTorch"
                : report.config.vendor}{" "}
          · 单张可见设备
        </p>
      </section>
      <section className={`verdict verdict-${status}`} aria-label="测试结论">
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
            查看异常 <ArrowRight size={18} />
          </button>
        ) : null}
      </section>
      <section className="metrics" aria-label="用例统计">
        <div>
          <strong className="positive">{counts.PASS}</strong>
          <span>通过</span>
        </div>
        <div>
          <strong className="negative">{counts.FAIL}</strong>
          <span>异常</span>
        </div>
        <div>
          <strong className="caution">
            {counts.NOT_RUN + counts.INCONCLUSIVE}
          </strong>
          <span>{counts.INCONCLUSIVE ? "未完成 / 未判定" : "未执行"}</span>
        </div>
        <div>
          <strong className="unknown">未确认</strong>
          <span>物理单元覆盖</span>
        </div>
      </section>
      <div className="results-layout">
        <section className="panel checks">
          <h2>算子检查</h2>
          <div className="tabs" role="group" aria-label="筛选检查结果">
            {[
              ["all", `全部 (${rows.length})`],
              ["fail", `异常 (${counts.FAIL})`],
              ["pending", `未完成 (${counts.NOT_RUN + counts.INCONCLUSIVE})`],
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
                  <th>检查项目</th>
                  <th>结果</th>
                  <th>说明</th>
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
                        "索引指向的输入值与返回值不一致。",
                        "值与索引不一致",
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!visible.length ? (
              <p className="no-rows">此筛选下没有用例。</p>
            ) : null}
          </div>
          <p className="table-note">
            <Info size={17} />
            按算子分组；点击查看用例。未执行不等于通过。
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
        测试范围{" "}
        <span>
          已尝试用例 {summary.attempted} / {rows.length}
        </span>
        <span>XID/RAS 未采集</span>
        <span>整卡健康 尚不能判断</span>
      </div>
      <PowerEvidence telemetry={report.telemetry} />
      <details className="report-details">
        <summary>设备、运行环境与原始证据</summary>
        <Definition
          items={[
            ["工具版本", report.tool_version],
            ["设备 UUID", report.identity?.uuid],
            ["计算设备", report.identity?.execution_device],
            ["框架版本", report.identity?.framework_version],
            ["运行时版本", report.identity?.runtime_version],
            ["报告状态", report.status],
            ["完整执行", report.complete],
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
