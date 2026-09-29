# 硬件测试看板（2.1 开发预览）

面向第一次做硬件自检的工程师：**先看结论，再看异常用例，最后按提示复测。**
看板与 agent 读取同一份 `self-test` JSON，不需要编写 Python，也不需要 Node.js。
这是 `codex/v2.1-hardware-selftest` 分支的预览功能，尚未发布到 2.0.0。

## 三步上手

在独立目录中取得开发分支，使用 Python 3.9+ 虚拟环境：

```bash
git clone --branch codex/v2.1-hardware-selftest https://github.com/phantom5125/omnismi.git
cd omnismi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[selftest]'
omnismi dashboard --open
```

打开终端给出的本地地址（默认 `http://127.0.0.1:8765`）。端口占用时增加
`--port 8766`，或者 `--port 0` 让系统分配。查看报告无需 GPU 或计算框架。

1. **开始自检**：选择目标型号、快速/扩展/负载检查。先复制计划命令确认范围。
2. **在目标机器执行**：预先安装厂商支持的计算运行时，复制自检命令。
   负载只在显式执行 `--run` 时启动。看板本身不会启动工作负载。
3. **导入报告**：把生成的 `selftest.json` 拖入看板或点击“导入报告”。
   退出码 2/3 的 JSON 同样需要保留；出现异常时也保留 `sdc-evidence` 中的 NPZ。

例如，在已配置兼容 CUDA PyTorch 的 RTX 5090 机器上：

```bash
omnismi self-test --plan --target rtx-5090 --profile smoke
omnismi self-test --run --target rtx-5090 --device 0 --profile smoke \
  --timeout 120 --artifact-dir ./sdc-evidence > selftest.json
omnismi dashboard --report selftest.json --open
```

`--device` 是计算运行时当前可见设备中的索引，一次测试一张设备/分区。
发现型号与 `--target` 不匹配时，在执行算子之前停止并返回 `INCONCLUSIVE`。
其他型号仍可使用 `--vendor` 的通用计划；无明确型号约束时不会假装已核对型号。
更多参数与预算见[硬件自检](hardware-selftest.md)。

如果没有测试机，点击“查看演示报告”。演示用合成的 topk 失败解释界面，
始终标为演示，导出的 JSON 也保留 `synthetic_demo=true`，不是实卡验证结果。

## 看懂结果

| 界面结论 | 意义 | 下一步 |
|---|---|---|
| 所选检查通过 | 本次计划内的检查和要求的验收条件通过 | 保留报告，扩大用例或重复次数 |
| 发现数值异常 | 数值、shape 或索引与 CPU 参考/算子要求不符 | 保存 JSON/NPZ，同卡复测，再换卡/框架版本对照 |
| 还不能得出结论 | 缺少运行时、算子不支持、预算不足或验收条件未满足 | 查看未完成原因和原始证据 |
| 这是一份测试计划 | 尚未执行任何计算 | 在目标机器执行生成的命令 |

- “通过/异常/未完成”统计的是**用例数**；默认表格按八类算子分组。
  筛选异常或未完成后逐个列出用例，右侧下拉框可切换同一算子的用例。
- sort 通过不会抵消 topk 异常。未执行和运行错误不会计入通过。
- 点击算子，查看 dtype、shape、k、seed 和中文原因；技术参数默认折叠。
- 复测保留报告的配置和 seed；固定输出位置，不把导入报告中的任意路径拼入命令。
  修改型号/参数会改变测试范围，逐输入回放仍需保存 NPZ。
- 只有报告含真实采样时才绘制功率曲线，并展示样本数和峰值。无采样不填零；
  未设置或未达到目标时，不宣称完成高功率验证。
- “XID/RAS 未采集”不等于“没有 XID/RAS”。当前没有硬件单元采样证明，
  **物理单元覆盖始终为未确认，整卡健康尚不能判断**。
- 数值异常可能来自硬件、驱动、框架、编译器或参考实现。软件报告不自动确诊硬件 SDC。

## 首批型号与验收顺序

首批覆盖消费者 Blackwell、数据中心 Blackwell Ultra、AMD 和 TPU 四类执行环境。
这是项目优先级，不是公开故障率或用户量排行榜。**以下执行路径已经接入，均待实卡验收。**

| 顺序 / 型号 | 参数 | 执行路径与精度 | 当前缺口 |
|---|---|---|---|
| 1. GeForce RTX 5090 | `--target rtx-5090` | CUDA PyTorch；扩展 FP32/FP16/BF16/INT32 | 真实框架组合、低精度及负载验收；SM 内部覆盖未知 |
| 2. NVIDIA B300 | `--target b300` | CUDA PyTorch；同上 | 真机、分区身份和 SM 采样；不代表整个 DGX 或 NVLink 链路 |
| 3. AMD Instinct MI355X | `--target mi355x` | ROCm PyTorch；同上 | 真机、HIP 算子和功率身份校验；CU 内部覆盖未知 |
| 4. Google TPU v6e | `--target tpu-v6e` | JAX/TPU；扩展 FP32/BF16/INT32，BF16 负载 | 真机、XLA 物理路径；无功率验收与整个 slice 覆盖保证 |

“精度覆盖”指用例矩阵，不表示所有该精度指令或所有计算单元都执行过。
通用的 `--vendor google` 计划保留原有行为；选择 `tpu-v6e` 才使用型号专属精度配置。
寒武纪路径保留但待确定卡型，PPU 的新 SDC 执行器仍待实现，不列入首批已完成验证。

每个型号依次：快速检查 → 扩展检查 → 重复扩展 → 有界负载 → 保存证据与运行时版本。
先在一张正常卡上验证可运行性和误报，再加入已知异常卡或可控错误注入的对照。
记录型号、UUID、可见性、驱动/框架版本、seed、功率归属与结果，才能把
`hardware_validation` 从 pending 更新为有证据支撑的状态。

### 选型与正确性资料

资料核对日期：2026-09-30。型号资料来自
[NVIDIA RTX 5090](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/)、
[NVIDIA DGX B300](https://docs.nvidia.com/dgx/dgxb300-user-guide/introduction-to-dgxb300.html)、
[AMD MI355X](https://www.amd.com/en/products/accelerators/instinct/mi350/mi355x.html)、
[Google TPU v6e](https://docs.cloud.google.com/tpu/docs/v6e) 和
[TPU BF16](https://docs.cloud.google.com/tpu/docs/bfloat16)。

公开正确性记录可以帮助选择回归用例，例如
[PyTorch #189567](https://github.com/pytorch/pytorch/issues/189567) 中的 CUDA 计算问题，
以及 [ROCm/aiter #4012](https://github.com/ROCm/aiter/issues/4012) 中 MI355X 上的模型精度差异。
它们涉及软件执行路径，**不能作为该型号硬件故障或 SDC 发生率的证据**。
本项目尚无可比较的卡型级故障率或用户规模数据。

## 本地数据与兼容性

服务仅监听 `127.0.0.1`，只提供打包的静态资源和显式 `--report` 选定的一份报告，
不浏览磁盘、不接受执行请求。报告经浏览器内校验后显示，最大 8 MiB，
支持 `schema_version=1`、`report_type=hardware_selftest`；不认识的版本或坏文件会显示错误，
并保留此前打开的报告。默认不写浏览器持久存储，不上传报告，不加载外部字体或遥测。
外部资料链接仅在主动点击时访问。报告刷新后需重新导入；启动时指定的报告会重新载入。

当前为单报告查看器，不是实时多卡监控、作业调度器或历史对比系统。
第一版中文 UI，后续再增加其他语言与现场执行体验。

## 维护前端

用户安装包已经带有构建产物；维护 UI 才需要 Node.js 22.12+：

```bash
cd frontend
npm ci
npm test
npm run build
```

开发时 `npm run dev`。构建写入 `src/omnismi/dashboard/static`，随源码和 wheel 一起提交。
CI 检查报告语义、命令生成、HTTP 边界、无计算依赖的 wheel 安装和构建产物一致性。
硬件测试仍需真实设备；CI 绿灯不代表上述型号已经实卡验收。
