import React, { useState } from "react";
import {
  Check,
  CheckCircle2,
  AlertCircle,
  CircleDashed,
  Copy,
  Terminal,
} from "lucide-react";

const statusText = {
  PASS: "通过",
  FAIL: "异常",
  INCONCLUSIVE: "未判定",
  NOT_RUN: "未执行",
};
export function Status({ status }) {
  const Icon =
    status === "PASS"
      ? CheckCircle2
      : status === "NOT_RUN"
        ? CircleDashed
        : AlertCircle;
  return (
    <span className={`status status-${status}`}>
      <Icon size={17} aria-hidden="true" />
      {statusText[status] || "未知"}
    </span>
  );
}
export function CopyButton({ text, label = "复制命令", primary = false }) {
  const [state, setState] = useState("");
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("已复制");
    } catch {
      setState("请选中下方命令后手动复制");
    }
  }
  return (
    <>
      <button
        className={primary ? "button primary" : "button"}
        onClick={copy}
        disabled={!text}
      >
        {state === "已复制" ? <Check size={16} /> : <Copy size={16} />}
        {state === "已复制" ? state : label}
      </button>
      <span className="sr-only" role="status">
        {state}
      </span>
      {state.startsWith("请") ? <p className="muted">{state}</p> : null}
    </>
  );
}
export function Command({ text }) {
  return (
    <div className="command">
      <Terminal size={18} aria-hidden="true" />
      <code>{text}</code>
    </div>
  );
}
export function Definition({ items }) {
  return (
    <dl className="definitions">
      {items.map(([label, value]) => (
        <React.Fragment key={label}>
          <dt>{label}</dt>
          <dd>{value == null || value === "" ? "未记录" : String(value)}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}
