# S01 本机环境审计

日期：2026-11-10，Asia/Shanghai。只读检查，尚未安装、下载或推理。

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

## 下一代码单元 S02

目标产物：一个最小脚本及项目内隔离环境说明，能够加载单一房间、保存初始 RGB、执行 3–5 个固定动作、记录每步是否成功、重置后重复，并在 `runs/` 中保存轨迹索引。预定命令形态为 `python scripts/smoke_sim.py --scene FloorPlan1 --output runs/smoke`；**脚本尚未创建，命令当前不可执行。**

S02 以真实图片、轨迹和重复重置结果验收；如果受下载、网络或兼容性阻断，记录具体边界，不称为跑通。
