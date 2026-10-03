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
  PASS: "Passed",
  FAIL: "Mismatch",
  INCONCLUSIVE: "Inconclusive",
  NOT_RUN: "Not run",
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
      {statusText[status] || "Unknown"}
    </span>
  );
}
export function CopyButton({ text, label = "Copy command", primary = false }) {
  const [state, setState] = useState("");
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setState("Copied");
    } catch {
      setState("Select the command and copy it manually.");
    }
  }
  return (
    <>
      <button
        className={primary ? "button primary" : "button"}
        onClick={copy}
        disabled={!text}
      >
        {state === "Copied" ? <Check size={16} /> : <Copy size={16} />}
        {state === "Copied" ? state : label}
      </button>
      <span className="sr-only" role="status">
        {state}
      </span>
      {state.startsWith("Select") ? <p className="muted">{state}</p> : null}
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
          <dd>
            {value == null || value === "" ? "Not recorded" : String(value)}
          </dd>
        </React.Fragment>
      ))}
    </dl>
  );
}
