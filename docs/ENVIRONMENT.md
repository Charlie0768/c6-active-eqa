# S01 本机环境审计

日期：2026-11-10，Asia/Shanghai。本节为 S01 的只读检查；S02 实测见下文。

| 项目 | 实测结果 | 解释 |
|---|---|---|
| 机器 | MacBook Air，Apple M4，10 核 | `system_profiler SPHardwareDataType -detailLevel mini` |
| 内存 | 16 GB | 同上；尚未测模型与 Unity 同时运行峰值 |
| 操作系统 | macOS 27.0.1 | `sw_vers -productVersion` |
| 架构 | arm64 | `uname -m` |
| 当前磁盘可用 | 约 190 GiB | `df -h .`；会随其他文件变化 |
| 系统 Python | 3.9.6 | `/usr/bin/python3 --version` |
| Conda Python | 3.13.5 | `/opt/anaconda3/bin/python -V` |
| Conda | 已安装 | `command -v conda` |
| 相关依赖 | 两个已检查 Python 环境均未找到 ai2thor、torch、transformers | `importlib.util.find_spec`；不代表别的环境也没有 |

`sysctl -n hw.memsize` 在当前执行环境被拒绝，故内存以 `system_profiler` 结果为准。`system_profiler` 初期出现 Activation Lock 检查超时提示，但随后返回了芯片和内存字段。

## 试跑路线

1. 在项目隔离环境中装最小仿真依赖，运行单房间固定动作；不改系统 Python 或 Conda base。
2. 如果 macOS/arm64 仿真不兼容，记录完整错误与版本，给本地排障约 4 团队工时上限，再选 Linux 云端。
3. 仿真成功后单独运行一张图的 Qwen3-VL 问答；2B Instruct 作为低资源技术试跑候选。4B 与本地并行运行是否合适，以实测决定。
4. 两条链路分别可用后再连接；正式实验使用一个固定的模型版本。

官方 [AI2-THOR 安装页](https://ai2thor.allenai.org/ithor/documentation/)给出 macOS 安装入口、首次 Unity 资源约 500 MB 下载及基本 `Controller` 调用，但未据此确认本机当前系统与 arm64 可运行。官方 [Qwen3-VL-2B-Instruct 模型卡](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)提供图像输入示例，但尚未在本机测试精度、量化、内存与推理时间。

## S02：本机仿真烟测（已执行）

在项目根目录用系统 Python 3.9 创建隔离环境，只安装 S02 的依赖：

```bash
/usr/bin/python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-s02.txt
./.venv/bin/python scripts/smoke_sim.py --scene FloorPlan1 --output runs/smoke
```

每次运行需给一个不存在或为空的输出目录。首次启动会下载 AI2-THOR 的 Unity 构建；本机实际下载包为约 775 MB，缓存于 `~/.ai2thor`。这台机器上使用的 `ai2thor==5.0.0` 可启动 macOS 的 `OSXIntel64` 构建并返回 RGB 帧；Python 进程仍为 arm64。运行不涉及 Qwen3-VL 或付费 API。

最终验收目录为 `runs/smoke-final/`（Git 忽略，保留在本机）：`summary.json`、`trace.jsonl` 和 12 张 300×300 PNG。两轮各从 `FloorPlan1` 开始，依次执行 `RotateRight → MoveAhead → RotateLeft → LookDown → LookUp`。两轮各 5/5 个动作成功；重置后对应步骤的动作结果、agent 位姿和帧尺寸均一致。每张 PNG 可打开，轨迹中的 SHA-256 与文件一致。一个可观察例子：初始画面朝向冰箱，`RotateRight` 后视野发生变化，脚本同时记录行动是否成功。

**复现边界：**重置后的 PNG 字节不完全一致；最终运行初始帧的平均绝对像素差约 22.38/255、最大单通道差 39。视觉上两张初始图均为同一冰箱视角，但不能把 RGB 哈希相同当作本环境的重置条件。烟测的通过门槛是动作反馈与 agent 位姿一致；后续评分不能依赖逐像素相等。完整逐步差异见 `runs/smoke-final/summary.json`。

受控执行环境的默认沙箱无法访问官方构建地址，也不能写 `~/.ai2thor` 锁文件；本次在允许网络和该缓存写入的执行环境中完成。用户在自己的终端按上面命令运行时通常不受此沙箱限制，但仍需正常网络、磁盘和 macOS 运行权限。
