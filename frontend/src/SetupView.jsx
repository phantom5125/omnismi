import React, { useState } from "react";
import { ArrowRight, Info } from "lucide-react";
import catalog from "../../src/omnismi/selftest/targets.json";
import { commandFor, defaultConfig } from "./report.js";
import { Command, CopyButton } from "./ui.jsx";

export default function SetupView({ initial, onImport }) {
  const [config, setConfig] = useState(
    () => initial || defaultConfig(catalog.targets[0]),
  );
  const target = catalog.targets.find((t) => t.id === config.target);
  function update(key, value) {
    setConfig((previous) => ({ ...previous, [key]: value }));
  }
  function chooseTarget(id) {
    const selected = catalog.targets.find((t) => t.id === id);
    setConfig((previous) => ({
      ...previous,
      target: selected.id,
      vendor: selected.vendor,
    }));
  }
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
      <h1>{initial ? "准备复测" : "开始一次自检"}</h1>
      <p className="lead">
        选择设备与测试范围，在目标机器执行命令，再把报告带回来查看。
      </p>
      <div className="workflow-layout">
        <section className="panel setup">
          <h2>1. 选择测试范围</h2>
          <label>
            目标型号
            <select
              value={config.target || ""}
              onChange={(e) => chooseTarget(e.target.value)}
            >
              {!config.target ? (
                <option value="">
                  通用 {config.vendor} 配置（保留原报告范围）
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
              "复用原报告的厂商配置。型号预设与厂商运行时编号是两件事。"}
          </p>
          <label>
            测试方案
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
              <option value="smoke">快速检查 · 首次使用</option>
              <option value="extended">扩展检查 · 更多精度与输入组合</option>
              <option value="soak">负载检查 · 计算与复查交错执行</option>
            </select>
          </label>
          <div className="form-grid">
            {[
              ["device", "运行时设备编号", 0, 4095],
              ["passes", "重复次数", 1, 100],
              ["timeout", "总时间预算 / 秒", 1, 3600],
              ["memory_mib", "张量预算 / MiB", 16, 4096],
            ].map(([key, label, min, max]) => (
              <label key={key}>
                {label}
                <input
                  type="number"
                  min={min}
                  max={max}
                  step="1"
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
            设备编号来自计算运行时，可能与总览编号不同。预算不包含框架工作空间；达到总时间上限会停止。
          </p>
          <details>
            <summary>复现与负载参数</summary>
            <label>
              随机种子
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
                  负载阶段时长 / 秒
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
                  观测功率目标 / W（可选）
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
                  这是验收条件，不会设置设备功率。无归属明确的采样或未达目标时，结果为未判定。
                </p>
              </>
            ) : null}
            <p className="field-help">
              复测保留 seed 与已记录的算子选择。证据写入
              ./sdc-evidence；逐输入回放仍需保留 NPZ 文件。
            </p>
          </details>
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
        </section>
        <section className="panel workflow-instructions">
          <h2>2. 在目标机器运行</h2>
          <p>
            先取得 2.1 开发分支源码，在仓库目录中安装，并配置匹配的计算运行时。
          </p>
          <Command text="python -m pip install -e '.[selftest]'" />
          <p>可先查看计划，不执行计算：</p>
          <Command text={plan || "请先修正左侧配置。"} />
          <CopyButton key={plan} text={plan} label="复制计划命令" />
          <p>确认范围后运行自检：</p>
          <Command text={run || "请先修正左侧配置。"} />
          <CopyButton key={run} text={run} label="复制自检命令" primary />
          <p className="field-help">
            这个看板不直接启动 GPU 负载。退出码 2/3
            也要保留报告，分别表示发现异常/尚不能判断。
          </p>
          <div className="next-steps">
            <h2>3. 查看测试结果</h2>
            <p>
              导入生成的 selftest.json。失败时同时保留 sdc-evidence
              中的数据文件。
            </p>
            <button className="button outline" onClick={onImport}>
              导入测试报告 <ArrowRight size={17} />
            </button>
          </div>
        </section>
      </div>
      <p className="notice">
        <Info size={18} />
        执行路径已接入；首批型号仍待实卡验收。负载检查不保证达到额定功率，单卡通过不代表所有硬件单元都健康。
      </p>
    </div>
  );
}
