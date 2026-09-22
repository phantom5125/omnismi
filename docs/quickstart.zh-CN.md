# 中文上手指南

[English quickstart](quickstart.md)

先在普通电脑上跑通离线诊断，再到加速卡机器配置厂商环境。核心包不要求
GPU、SDK 或 PyTorch。以下安装命令适用于 Linux / macOS，要求 Python 3.9+；
Python 3.12 是已经测试的起点。实时 sysfs 拓扑采集和 SDK 编译需要 Linux。

## 1. 安装 2.0 开发预览版

[PyPI 上的发布版](https://pypi.org/project/omnismi/)目前是 1.0.0，不包含下面的
预览命令。体验新功能请安装对应源码分支：

```bash
git clone --branch codex/v2-runtime-completion --single-branch https://github.com/phantom5125/omnismi.git
cd omnismi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

已经在这个分支的项目目录中，就从创建虚拟环境开始。后续相对路径均以项目
根目录为准。开发包暂未修改版本号，仍显示 1.0.0，可以这样确认预览命令可用：

<!-- quickstart-smoke: help -->
```bash
python -m omnismi decode --help
```

只需要已发布的 Python 查询 API，可以在另一个虚拟环境安装
`omnismi`、`omnismi[nvidia]` 或 `omnismi[amd]`。这与安装预览版是两条不同路径。

## 2. 不用显卡，获得第一份诊断结果

<!-- quickstart-smoke: decode -->
```bash
python -m omnismi decode --vendor nvidia --namespace xid --code 48
```

预期得到 JSON：`status` 为 `FAIL`，`data.findings` 包含错误解释和建议检查，
`sources` 列出规则来源，而 `scope.current_hardware_health` 为 `INCONCLUSIVE`。

这个命令的退出码是 **2**，表示输入事件的严重程度；命令本身正常执行了。
它没有检测你的显卡，也不表示当前机器存在硬件故障。解释过程不访问网络，
不调用 LLM，也不用在运行时翻阅白皮书。

再试一下仓库附带的模拟日志：

<!-- quickstart-smoke: log -->
```bash
python -m omnismi diagnose --input examples/diagnostics/xid48.log
```

预期为 `FAIL`、退出码 2，证据中保留日志的 PCI 身份。之后可以把路径换成
自己已经采集的日志。对于未知错误码：

<!-- quickstart-smoke: unknown -->
```bash
python -m omnismi decode --vendor nvidia --namespace xid --code 999999
```

预期为 `INCONCLUSIVE`、退出码 3，不会套用其他错误的解释。
更多输入格式、AMD RAS 和 PPU 代际选择见[诊断指南](v2/diagnostics.md)。

## 3. 体验“达到预期百分之几”

<!-- quickstart-smoke: performance -->
```bash
python -m omnismi perf-doctor --input examples/performance/synthetic-measurement.json --baseline examples/performance/synthetic-baseline.json
```

预期：达到持续性能预期的 **80%**、理论峰值的 **40%**，按示例策略得到
`WARN`、退出码 **1**。这些是用于演示计算的模拟数据，不是任何卡的真实基准。
真实采样、运行条件和基准维护方法见[性能指南](v2/perf-doctor.md)。

## 4. 接入实际硬件

在驱动/SDK 已配置的机器上，从当前源码目录安装对应后端：

| 硬件 | 前置环境与安装 | 只读查询 |
|---|---|---|
| NVIDIA | 驱动正常；`python -m pip install '.[nvidia]'` | `omnismi --vendor nvidia -o json` |
| AMD | ROCm/AMD SMI 匹配；`python -m pip install '.[amd]'` | `omnismi --vendor amd -o json` |
| Google TPU | TPU VM；`python -m pip install '.[tpu]'` | `omnismi --vendor google -o json` |
| 阿里 PPU | SAIL SDK，PATH 中有 `ppu-smi`；[配置指南](v2/alibaba-ppu.md) | `omnismi --vendor alibaba -o json` |
| 寒武纪 MLU | CNDEV 头文件、库和 C 编译器；[编译采集器](v2/cambricon.md) | `omnismi --vendor cambricon -o json` |

Omnismi 不自动安装驱动、SDK 或计算框架。设备数量、依赖或容器可见性有疑问时，
运行 `omnismi doctor`。Linux 上可运行 `omnismi topology` 查看本地拓扑；安装了
厂商管理工具后，可追加 `--collect-vendor nvidia` 或 `--collect-vendor alibaba`。

## 5. 显式启动自检和性能测试

管理信息查询不依赖 PyTorch。运行负载时，NVIDIA/AMD 需要匹配的 torch，
寒武纪需要 torch_mlu，PPU 需要通过 `omnismi sail-build` 编译原生 HGGC 探针。
对应配置见各厂商指南。

确认计算运行时能看到目标卡，并希望执行负载时：

```bash
omnismi bench suite --vendor nvidia --device 0 --memory-mib 64 --timeout 90
```

将 vendor 换成实际厂商。这里的 `--device` 是**计算运行时编号**，不一定与
总览的全局编号一致。套件顺序执行自检、拷贝带宽、向量带宽和 FP32 矩阵乘法，
共用超时预算；某一步不能通过时，会记录并跳过后续步骤。PASS 表示执行的
正确性检查通过，不代表整卡健康或达到预期性能。

## 脚本和 agent 如何处理结果

新命令 `decode`、`diagnose`、`perf-doctor`、`topology`、`bench matmul/suite`
默认输出 JSON，退出码如下：

| 退出码 | 含义 |
|---|---|
| 0 | PASS，或成功生成基准 |
| 1 | WARN |
| 2 | FAIL：输入证据或执行的检查发现问题 |
| 3 | INCONCLUSIVE：证据、运行时、支持范围或基准不足 |
| 64 | 参数/输入有误，查看 stderr |

退出码 0–3 的 stdout 都应保留。直接使用 `check=True`、`set -e` 或 `&&`
可能让脚本在示例的预期 WARN/FAIL 处中断。总览、doctor 和旧的
`bench bandwidth` 保持原来的退出行为。

Python agent 可以直接调用库：

```python
from omnismi.diagnostics import decode_error

report = decode_error("nvidia", "xid", 48)
print(report["status"])
print(report["data"]["findings"])
```

## 常见问题

| 现象 | 排查方法 |
|---|---|
| 找不到 `omnismi` | 激活虚拟环境，或使用安装它的解释器运行 `python -m omnismi`。 |
| 不认识 `decode` | 检查是否安装了 PyPI 1.0.0；在当前虚拟环境安装预览分支源码。 |
| 设备数为 0 / 指标为 null | 运行 `omnismi doctor`，检查后端依赖、驱动和容器权限；这不是健康判定。 |
| 无权读取 dmesg/sysfs | 使用有权限取得的日志文件进行离线诊断；空证据不代表健康。 |
| PPU 提示缺少原生探针 | 在 SDK 主机执行 `omnismi sail-build`，设置 `OMNISMI_SAIL_PROBE`。 |
| 寒武纪采集器不可用 | 按指南执行 `omnismi cndev-build`，设置 `OMNISMI_CNDEV_PROBE`。 |
| 性能结果 INCONCLUSIVE | 先看原因：运行时不可用、缺运行条件、缺基准各有不同处理办法；采样成功但不可比较时仍可保存数据。 |

本页的离线命令由 CI 使用安装后的 wheel 实际执行。PPU/MLU 的真实
SDK 编译和实卡运行仍待验证；状态以[兼容矩阵](compatibility.md)和
[2.0 交付状态](v2/STATUS.md)为准。
