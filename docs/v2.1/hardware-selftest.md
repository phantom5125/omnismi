# 2.1 硬件自检：SDC 检测开发分支

状态：**2.1.0.dev0 开发预览，尚未发布 2.1.0**。分支为
`codex/v2.1-hardware-selftest`。2.0 的 `diagnose --self-test` 保持原有有界探测；
本页介绍新的 `omnismi self-test` CPU 参考比对流程。

## 产品边界

自检是 Omnismi 工具的一项跨厂商工作流。用户和 agent 使用相同的测试计划、
结果语义和证据，不必自己维护多套厂商诊断脚本。Python API 是集成入口之一，
当前使用 Python 分发也不要求用户编写 Python 程序。

PyTorch、JAX 和厂商 SDK 是计算执行后端；Omnismi 负责用例、独立参考、超时、
复现材料及覆盖结论。原生内核用于取得诊断所需的硬件证据，不扩展为通用张量框架。
详见[产品定位](../why-omnismi.md)和[路线图](../roadmap.md)。
当前自检输出为 JSON；面向人的摘要和统一能力发现仍是待实现的工具接口。

目标是发现没有伴随 XID/RAS 的错误计算，包括特定算子触发、重复运行才出现、
或负载变化时出现的异常。项目 owner 提供过 Blackwell 上 sort 正常而 topk
暴露异常的案例，但原始参数已不可用；本项目将它作为测试设计动机，
不声称已复现该事件或确定了根因。

## 首版已实现什么

- 独立 CPU 输入和参考值，检查每一次执行的完整返回数组。
- copy、add、mul、sum、gather、sort、topk、matmul 八类算子。
- topk 单独覆盖，不用 sort 的结果代替：检查返回值、索引范围、唯一性、
  值与原输入的对应关系，以及 CPU 排序产生的目标值集合。
- smoke、extended、soak 三个配置；可指定 seed、passes、算子集合、预算和超时。
- extended 覆盖 FP32、FP16、BF16、INT32 的选择算子，以及合法的浮点计算组合；
  奇偶长度、2 的幂及邻近长度、k=1/中间值/全长、升降序、重复值和步长视图。
- soak 使用较大的 FP16 稠密矩阵乘法，每次都回传 CPU 校验，穿插 topk，
  完成后再跑一轮算子检查；首次数值不匹配即停止并保留证据。
- 单独子进程、总时间预算、原子进度文件，超时/崩溃保留已观察到的 FAIL。
- 可选 NPZ 失败输入/输出归档；JSON 记录 dtype、shape、k、方向、布局、seed、
  迭代、输入 SHA256、框架版本与设备身份。
- 可选功率观测；只有 runtime UUID 和监控 UUID 精确匹配时才归属到该设备。

**尚未完成“扫描每一个硬件单元”。** 当前没有原生 SM/CU/MLU/PPU 单元采样器，
也没有完整显存地址、缓存、寄存器、Tensor Core 或链路的覆盖证明。
`physical_units.status` 始终为 `UNKNOWN`。设置 `--require-unit-coverage`
会使没有数值错误的运行返回 `INCONCLUSIVE`，而不是伪造覆盖率。

## 在开发分支上运行

从本分支源码安装；以下新命令不属于 PyPI 的 2.0.0：

```bash
git switch codex/v2.1-hardware-selftest
python -m pip install -e '.[selftest]'
python -m omnismi self-test --plan --vendor nvidia --profile extended
```

`--plan` 不导入 NumPy、PyTorch、JAX，不启动设备工作负载，core-only 安装也可运行。
必须显式选择 `--plan` 或 `--run`。`--device` 是框架当前可见设备中的索引，
受容器和可见性变量影响，**不是** `omnismi.gpu()` 的全局索引。
一次调用只测试一张可见设备/分区，多卡需逐张运行并分别保存报告。

在已经装好兼容 CUDA PyTorch 的 NVIDIA 测试机上：

```bash
python -m omnismi self-test --run --vendor nvidia --device 0 \
  --profile smoke --timeout 120 --artifact-dir ./sdc-evidence > smoke.json

python -m omnismi self-test --run --vendor nvidia --device 0 \
  --profile extended --passes 3 --seed 42 --timeout 600 \
  --artifact-dir ./sdc-evidence > extended.json

python -m omnismi self-test --run --vendor nvidia --device 0 \
  --profile soak --duration 300 --timeout 900 --memory-mib 256 \
  --artifact-dir ./sdc-evidence > soak.json
```

`--timeout` 包含框架初始化、CPU 参考计算、所有 passes、负载与负载后检查；
`--duration` 只指定交错负载阶段的墙钟时长。默认 extended/soak 矩阵较大，
较慢的机器需要增大总预算。超时上限 3600 秒，负载阶段上限 1800 秒。
`--memory-mib` 是保守的测试张量预算，不是进程 RSS 或驱动工作空间硬上限；
超出预算的用例标为 `INCONCLUSIVE`，不会偷偷改小 shape 后宣称覆盖原用例。

需要判断实际功率时，在已安装相应监控后端、已知目标值的测试机上加
`--power-target-w <瓦数>`。这不是设置功率上限。至少需要 3 个新鲜的负载阶段样本，
且至少 80% 达到该值，功率验收才通过。UUID 无法匹配、监控缺失或未达到目标，
结果均为 `INCONCLUSIVE`。不要把其他卡、父卡或缓存中的旧读数计入目标卡。

交错负载包含 CPU 校验和 topk 间隙，**不保证持续达到 TDP**，也不是专用的电流
脉冲测试。0.5 秒软件采样无法证明捕获瞬态功率尖峰。功率目标未指定时，
数值检查可以 PASS，但不代表“已通过高功率验证”。

## 厂商与执行路径

| 厂商 | 2.1 当前路径 | 验证状态与缺口 |
|---|---|---|
| NVIDIA | CUDA PyTorch，显式同步；FP32 禁用 TF32 | CPU 适配测试完成；Blackwell/其他卡尚未上卡验收，SM 覆盖未知 |
| AMD | ROCm PyTorch，校验 HIP 构建，禁止 CUDA/ROCm 混用 | 共享适配器 CPU 测试完成；尚未上 AMD 卡验收，CU 覆盖未知 |
| 寒武纪 | `torch_mlu`、`torch.mlu` | 路径已接入；具体卡型与 SDK 算子支持尚未验证，不支持的用例为 INCONCLUSIVE |
| TPU | JAX 的显式本地 TPU device，exact `lax.top_k`，阻塞读取结果 | JAX CPU 适配测试完成；尚未 TPU 验收，不代表整个 TPU slice |
| 阿里 PPU | 新 SDC 原生执行器待实现 | 返回 INCONCLUSIVE；2.0 SAIL copy/add/matmul 探测不计作新覆盖矩阵 |

框架不会自动下载安装，不提供“声称在 GPU 测试但悄悄回退 CPU”的选项。
先在设备上使用厂商支持的 PyTorch/ROCm/torch_mlu/JAX 发行版，再安装此分支。
测试内部有 CPU adapter harness，仅用于验证代码合同，不是产品执行后端。

JAX/XLA 自行决定物理存储与编译后的执行方式，所以 TPU 计划只列逻辑连续输入；
copy 也可能被编译器优化掉，不能据此声称执行了特定 DMA 或内存硬件指令。
JAX 的 exact top_k 返回有序值，即使 `sorted=False` 也不代表覆盖了独立的无序内核。
所有框架路径都需通过原生插桩/剖析确认实际硬件路径后，才能扩大覆盖声明。

## 如何解释 JSON

| 字段/结果 | 含义 |
|---|---|
| `status=PASS`，退出码 0 | 所选计划的比较和显式要求的验收条件通过；不等于整卡健康 |
| `status=FAIL`，退出码 2 | 观察到数值、shape 或索引不符合 CPU 参考/算子合同；保留首次失败 |
| `status=INCONCLUSIVE`，退出码 3 | 运行时缺失、不支持、预算/时间不足，或覆盖/功率验收不足 |
| 退出码 64 | 参数值或启动文件操作错误；argparse 语法错误使用标准退出码 2 |
| `complete` | 执行流程是否跑完；跳过/不支持的用例仍需检查 status 和 acceptance_gates |
| `coverage.completed_cases` | 完成所要求次数且比较均通过的计划用例数；不是物理单元百分比 |
| `coverage.comparison_count` | 实际完成的数组比较次数，包括失败比较及负载检查 |
| `hardware_fault_confirmed=false` | 数值异常可能来自硬件、框架、编译器、驱动或参考实现，尚未归因 |
| `current_hardware_health=INCONCLUSIVE` | 有限测试不证明硬件完全健康 |

没有 XID 是用户提供的故障特征之一。新流程不依赖错误日志才能 FAIL；当前也不主动
读取事件日志，不能把“没有采集 XID”描述成“确认没有 XID”。可另外运行 2.0 的
`diagnose --input ...`，将两份证据关联到相同设备和时间。

重复值 topk 不要求 CPU/GPU 返回相同的 tied index 顺序；仍要求索引唯一、合法，
值和原输入相符，选出的值集合正确。PyTorch 官方明确说明 tied indices 不保证稳定。
[PyTorch topk 文档](https://docs.pytorch.org/docs/2.14/generated/torch.topk.html)

输入在 CPU 上先量化到目标 dtype，避免把输入量化误差当成计算错误。当前矩阵乘法
使用小整数输入，CPU 使用 FP64 参考；FP16/BF16 矩阵输出的相对容差分别为 0.001/0.008，
绝对容差为 0。其他当前用例使用数值精确比较，拒绝非预期 NaN/Inf。
这不是所有浮点工作负载的通用误差界：当前不覆盖 NaN 输入、溢出、subnormal、
FP8/INT8、所有 exponent/mantissa 位模式、卷积、原子操作和通信 collective。
当前 selection 用例为二维张量的最后一维；任意 rank/dim、更多长向量与特殊数值
语义的覆盖仍需补齐，不能视为已重现参数未知的原始 Blackwell 用例。
容差范围内的错误可能逃逸；后续应加入整数精确算术及多参考交叉检验。
[PyTorch 数值精度说明](https://docs.pytorch.org/docs/2.14/notes/numerical_accuracy.html)

发现异常后保存 JSON 和 NPZ。NPZ 含 `a`、`b`、`expected`、`actual`、`indices`，
可用 `numpy.load(path, allow_pickle=False)` 读取。用报告中的 case 和 seed 在同卡、
另一张同型卡、另一套框架版本上重复；再结合厂商诊断和错误日志定位归因。
比较错误在归档之前就已写入进度文件，磁盘写入失败不会清除 FAIL。

## 后续分阶段验收

1. **算子回归与复现**（本分支）：错误注入、PyTorch/JAX CPU 合同测试、安装和 CLI；
   随后采集一张正常卡和已有异常卡的 smoke/extended/soak 报告，形成硬件验收样本。
2. **原生执行与覆盖采样**：CUDA/ROCm worker 记录每个工作负载实际出现的 SM/CU ID；
   按输入块保留失败位置，区分“调度单元出现过”与“内部 ALU/寄存器等全部测试过”。
   NVIDIA `%smid` 的 ID 不保证连续，`%nsmid` 也不是实际 SM 数量，不能直接用
   `range(SM_count)` 作为必达集合。
   [PTX 特殊寄存器文档](https://docs.nvidia.com/cuda/parallel-thread-execution/#special-registers-smid)
3. **功率条件下的检查**：连续大矩阵负载与独立比较流并发、显式 idle/load 转换、
   测量实际功率/温度/时钟，保留每份被验证的输出；未验证的中间结果不能计入覆盖。
   专用电流脉冲能力需逐 SKU 验收，普通功率轮询不替代它。
   [DCGM Pulse Test](https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/diag-pulse-test.html)
4. **PPU/MLU/TPU 原生扩展**：PPU 使用 SAIL/HGGC 实现 selection 与计算/内存测试，
   寒武纪依据可用 SDK 及卡型实现原生单元标识；TPU 区分本地 device、core、slice。
   每种后端都要运行同一套 host oracle 合同和错误注入，并记录无法观测的单元。
   [T-Head 开发者中心](https://developer.t-head.cn/home)、
   [HGGC 编程文档](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=39&chapterId=196)、
   [JAX exact top_k](https://docs.jax.dev/en/latest/_autosummary/jax.lax.top_k.html)、
   [JAX 异步执行说明](https://docs.jax.dev/en/latest/async_dispatch.html)。

发布 2.1.0 前，必须明确目标 SKU/SDK 的实测矩阵、故障检测样本和覆盖限制。
CI 的 CPU 合同测试不能作为 NVIDIA、AMD、MLU、PPU 或 TPU 的硬件认证。
