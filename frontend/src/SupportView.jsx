import React from "react";
import { ArrowUpRight, ArrowRight } from "lucide-react";
import catalog from "../../src/omnismi/selftest/targets.json";

export function SupportView({ onSelect }) {
  return (
    <div className="workflow-page">
      <h1>首批适配计划</h1>
      <p className="lead">
        先把少数型号测清楚，再逐步扩展。执行路径与实卡验收分开记录。
      </p>
      <div className="support-list">
        {catalog.targets.map((target) => (
          <article className="panel target" key={target.id}>
            <div className="target-heading">
              <div>
                <span className="muted">
                  优先级 {target.priority} · {target.family}
                </span>
                <h2>{target.name}</h2>
              </div>
              <span className="pending-label">待实卡验收</span>
            </div>
            <div className="target-columns">
              <div>
                <h3>重点检查</h3>
                <p>{target.focus}</p>
                <p className="muted">{target.runtime} · 执行路径已接入</p>
              </div>
              <div>
                <h3>仍未覆盖</h3>
                <p>{target.gaps}</p>
              </div>
            </div>
            <div className="target-footer">
              <div>
                {target.sources.map((source) => (
                  <a
                    key={source.url}
                    href={source.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {source.label}
                    <ArrowUpRight size={14} />
                  </a>
                ))}
              </div>
              <button className="button" onClick={() => onSelect(target)}>
                生成测试命令
                <ArrowRight size={16} />
              </button>
            </div>
          </article>
        ))}
      </div>
      <p className="muted">
        资料核对：{catalog.reviewed_at}
        。选择依据是当前项目优先级与运行时差异，不是故障率排名；公开精度问题不能直接作为硬件
        SDC 的证据。尚无可比的用户量或讨论热度统计。
      </p>
    </div>
  );
}

export function GuideView({ onSetup }) {
  return (
    <div className="workflow-page guide">
      <h1>先读懂结果，再判断硬件</h1>
      <p className="lead">不需要先读白皮书。用这四个问题理解一份报告。</p>
      <section className="panel">
        <h2>1. 测了什么？</h2>
        <p>
          先看设备、方案和用例数量。“通过 7
          项”描述的是本次完成的检查，不是硬件健康度 7
          分，也不代表测试了每个计算单元。
        </p>
      </section>
      <section className="panel">
        <h2>2. 颜色代表什么？</h2>
        <dl className="guide-states">
          <dt className="positive">通过</dt>
          <dd>返回结果符合 CPU 参考或声明的容差。</dd>
          <dt className="negative">异常</dt>
          <dd>数值、形状或索引不符合要求，需要保存证据并复测。</dd>
          <dt className="caution">未判定</dt>
          <dd>运行时、时间、支持范围或验收证据不足。</dd>
          <dt>未执行</dt>
          <dd>这个用例还没运行。发现首个异常后，其余用例也可能没有执行。</dd>
        </dl>
      </section>
      <section className="panel">
        <h2>3. 精度差异就是 SDC 吗？</h2>
        <p>
          不是。FP16/BF16
          的表示范围和舍入会产生合理差异；检查必须有合适的参考与容差。超出预期也可能由框架、编译器或驱动造成。SDC
          指没有明显报错的错误计算，数值不匹配只是候选线索，不能单独确认硬件损坏。
        </p>
        <p>
          topk
          在重复值处可能返回不同但合法的索引。本工具会验证值、索引和选中集合，而不是强制每个索引都和
          CPU 一样。
        </p>
      </section>
      <section className="panel">
        <h2>4. 发现异常后怎么做？</h2>
        <ol>
          <li>导出 JSON，并保留失败输入/输出 NPZ。</li>
          <li>用同一配置在同卡重复，记录环境版本。</li>
          <li>换一张同型号卡或更换框架版本对照。</li>
          <li>结合厂商诊断与 XID/RAS 日志定位，不直接把数值异常归因为硬件。</li>
        </ol>
        <button className="button primary" onClick={onSetup}>
          准备一次自检
        </button>
      </section>
      <p className="muted">
        报告只在本地浏览器解析，不上传到云端。页面刷新会清除手动导入的数据；使用
        dashboard --report
        可在启动时载入一份报告。本看板不采集实时指标，不执行测试命令。
      </p>
    </div>
  );
}
