import React, { useState } from "react";
import { ArrowRight, Info } from "lucide-react";
import catalog from "../../src/omnismi/selftest/targets.json";
import { commandFor, defaultConfig } from "./report.js";
import { Command, CopyButton } from "./ui.jsx";

export default function SetupView({ initial, retest, onImport }) {
  const [config, setConfig] = useState(
    () => initial || defaultConfig(catalog.targets[0]),
  );
  const target = catalog.targets.find((t) => t.id === config.target);
  const update = (key, value) => setConfig((c) => ({ ...c, [key]: value }));
  let run = "",
    plan = "",
    error = "";
  try {
    run = commandFor(config, catalog.targets);
    plan = commandFor(config, catalog.targets, "--plan");
  } catch (err) {
    error = err.message;
  }
  return (
    <div className="workflow-page">
      <h1>{retest ? "Prepare a retest" : "Start with a quick check"}</h1>
      <p className="lead">
        Choose a device, run the command, then open the report.
      </p>
      <div className="workflow-layout">
        <section className="panel setup">
          <h2>1. Choose your test</h2>
          <label>
            Hardware model
            <select
              value={config.target || ""}
              onChange={(e) => {
                const t = catalog.targets.find((t) => t.id === e.target.value);
                setConfig((c) => ({ ...c, target: t.id, vendor: t.vendor }));
              }}
            >
              {!config.target ? (
                <option value="">
                  Generic {config.vendor} · Original scope
                </option>
              ) : null}
              {catalog.targets.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <p className="field-help">
            {target?.requirements ||
              "Uses the vendor and scope from your report."}
          </p>
          <label>
            Test profile
            <select
              value={config.profile}
              onChange={(e) =>
                setConfig((c) => ({
                  ...c,
                  profile: e.target.value,
                  timeout: e.target.value === "smoke" ? 120 : 900,
                  duration: e.target.value === "soak" ? 300 : 60,
                  power_target_w: null,
                }))
              }
            >
              <option value="smoke">Quick · Start here</option>
              <option value="extended">
                Extended · More inputs and data types
              </option>
              <option value="soak">Load · Compute bursts with rechecks</option>
            </select>
          </label>
          <div className="form-grid">
            {[
              ["device", "Runtime device index", 0, 4095],
              ["passes", "Repetitions", 1, 100],
              ["timeout", "Time limit (seconds)", 1, 3600],
              ["memory_mib", "Tensor budget (MiB)", 16, 4096],
            ].map(([key, label, min, max]) => (
              <label key={key}>
                {label}
                <input
                  type="number"
                  min={min}
                  max={max}
                  step={key === "timeout" ? "any" : "1"}
                  value={config[key]}
                  onChange={(e) =>
                    update(
                      key,
                      e.target.value === "" ? "" : Number(e.target.value),
                    )
                  }
                />
              </label>
            ))}
          </div>
          <p className="field-help">
            Use the index shown by your compute runtime. The memory budget
            excludes framework workspace.
          </p>
          <details>
            <summary>Advanced settings</summary>
            <label>
              Random seed
              <input
                type="number"
                min="0"
                max="4294967295"
                value={config.seed}
                onChange={(e) => update("seed", Number(e.target.value))}
              />
            </label>
            {config.profile === "soak" ? (
              <>
                <label>
                  Load duration (seconds)
                  <input
                    type="number"
                    min="0"
                    step="any"
                    max="1800"
                    value={config.duration}
                    onChange={(e) => update("duration", Number(e.target.value))}
                  />
                </label>
                <label>
                  Power target (W, optional)
                  <input
                    type="number"
                    min="0"
                    step="any"
                    value={config.power_target_w ?? ""}
                    onChange={(e) =>
                      update(
                        "power_target_w",
                        e.target.value === "" ? null : Number(e.target.value),
                      )
                    }
                  />
                </label>
                <p className="field-help">
                  An observation goal, not a power setting. Missing samples or
                  an unmet target make the result inconclusive.
                </p>
              </>
            ) : null}
            <p className="field-help">
              Retests preserve the seed and operator selection. Keep the NPZ
              files to replay the exact failing inputs.
            </p>
          </details>
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
        </section>
        <section className="panel workflow-instructions">
          <h2>2. Run on your test machine</h2>
          <p>
            In the 2.1 source checkout, install Omnismi. Set up a compatible
            vendor runtime first.
          </p>
          <Command text="python -m pip install -e '.[selftest]'" />
          <p>Preview the plan without starting a workload:</p>
          <Command text={plan || "Fix the settings to create a command."} />
          <CopyButton key={plan} text={plan} label="Copy plan command" />
          <p>Run the test and save its report:</p>
          <Command text={run || "Fix the settings to create a command."} />
          <CopyButton key={run} text={run} label="Copy test command" primary />
          <p className="field-help">
            Keep the report even if the command exits with code 2 (mismatch) or
            3 (inconclusive).
          </p>
          <div className="next-steps">
            <h2>3. Read the results</h2>
            <p>
              Open selftest.json here. Keep sdc-evidence too if a check fails.
            </p>
            <button className="button outline" onClick={onImport}>
              Import test report <ArrowRight size={17} />
            </button>
          </div>
        </section>
      </div>
      <p className="notice">
        <Info size={18} />
        Real-device validation is pending. This page creates commands; it does
        not start a workload.
      </p>
    </div>
  );
}
