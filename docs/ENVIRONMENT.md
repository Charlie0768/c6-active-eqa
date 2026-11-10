# 本机环境审计与 S02–S04 实测

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

## S03：Qwen3-VL 单图烟测（已执行）

用独立 Python 3.11 环境运行本地 MLX 推理，不给模型任何仿真 metadata：

```bash
/opt/anaconda3/envs/dl_pytorch/bin/python -m venv .venv-vl
./.venv-vl/bin/python -m pip install -r requirements-s03.txt
```

团队其他机器可尝试用自己的 Python 3.11/3.12 创建该环境；本工作单只在当前 Python 3.11.14 上验证。模型为公开的 [MLX 社区 Qwen3-VL-2B-Instruct-4bit](https://huggingface.co/mlx-community/Qwen3-VL-2B-Instruct-4bit)，修订版 `9c4f5209e57b31f4b9dfba735de3fb983739c9cc`。下载前通过 Hugging Face API 实测仓库 16 个文件合计 1,798,023,774 字节；实际模型目录约 1.7 GiB、隔离环境约 815 MiB，低于本工作单约 5 GB 的新增文件停止线。公开模型通过下面命令下载到 Git 忽略的 `models/`：

```bash
HF_HOME=.cache/huggingface HF_HUB_DISABLE_IMPLICIT_TOKEN=1 ./.venv-vl/bin/python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="mlx-community/Qwen3-VL-2B-Instruct-4bit",
    revision="9c4f5209e57b31f4b9dfba735de3fb983739c9cc",
    local_dir="models/qwen3-vl-2b-instruct-4bit",
    max_workers=2,
    token=False,
)
PY
```

`scripts/smoke_vl.py` 验证本地权重 SHA-256 为 `4750d95a2162829e127a94e83ac350d498d02070aab216c4687da48804a06ffb`，然后只把图片路径和固定问题交给模型。重跑时为 `--output` 指定新的空目录，例如：

```bash
HF_HOME=.cache/huggingface HF_HUB_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 ./.venv-vl/bin/python scripts/smoke_vl.py --image runs/smoke-final/run1_step00.png --model models/qwen3-vl-2b-instruct-4bit --output runs/s03-one-image-new
```

本机实际输出在 `runs/s03-one-image-accepted/result.json`（Git 忽略）：图片 SHA-256 与 S02 轨迹首帧一致，格式化提示词含一个图像占位符；136 个输入 token、28 个输出 token。模型答 `{"answer":"是","evidence":"冰箱在画面中央，清晰可见"}`，与保存的画面可人工核对。原文有 Markdown JSON 代码围栏，脚本保留原文、标注去围栏后解析成功。首次运行的模型加载约 1.37 秒、生成约 3.53 秒；后续验收运行分别约 0.90 秒、0.98 秒。MLX 报告峰值内存约 2.039 GB；单次推理均低于 10 分钟停止线。进程 RSS 与 MLX 内存口径不同，不相加当作总占用。付费 API/GPU 开销为 0。

这只证明该社区量化 checkpoint 在这张 300×300 图上能答题，不证明其他图片的准确率、它与原版的等价性、正式实验模型已选定或与 AI2-THOR 同时运行稳定。默认沙箱隔离 Metal GPU，本次在允许本机 GPU 的受控执行环境中实测。MLX-VLM 的[本地安装和图像推理示例](https://github.com/Neywa-Labs/mlx-vlm/blob/main/README.md)是实现参考。

## S04：一次真实行动的最小闭环（已执行）

在 S03 的 Python 3.11 `.venv-vl` 中增加 AI2-THOR 5.0.0：

```bash
./.venv-vl/bin/python -m pip install -r requirements-s04.txt
HF_HOME=.cache/huggingface HF_HUB_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 ./.venv-vl/bin/python scripts/one_step_episode.py --model models/qwen3-vl-2b-instruct-4bit --output runs/s04-one-step-new
```

每次给 `--output` 一个新目录。最终实测记录在被 Git 忽略的 `runs/s04-one-step-verified/episode.json`，同目录有 `frame1.png` 与 `frame2.png`。`FloorPlan1` 首帧正对冰箱，脚本先扣 1/1 行动预算，再执行固定 `RotateRight`；行动成功，第二帧主要看到门。模型只收到这两张已观察图、问题、动作名／成功标志和预算，回答 `{"answer":"是","evidence_frame":1}`。人工检查两张图，证据帧号与可见冰箱一致。此次动作由脚本固定，不是模型选择的探索策略；没有进行正式评分。

首次试跑模型返回 `answer` 和 `evidence_frame`，省略了原先要求的 `evidence` 文本字段，因此格式验收失败；记录保留在 `runs/s04-one-step/episode.json`。S04 将最小输出契约收窄为答案与证据帧号后重跑通过。两项边界测试检查：预算在仿真调用前扣减、第二次行动被阻止；隐藏的对象清单和答案无法进入模型输入白名单。

最终一次 episode 在当前 Mac 上的计时：Unity 启动 2.980 秒、取图及行动 0.020 秒、模型加载 0.883 秒、生成 0.989 秒、清理前合计 4.873 秒。MLX 报告峰值内存 2.277 GB；Unity 在模型前后均存活，取样 RSS 分别约 633 MB 和 367 MB。RSS 只是两次采样，不能当作 Unity 真正峰值；MLX 内存与进程 RSS 口径也不能直接相加。此结果证明一次同机并行闭环可运行，不代表连续多 episode 稳定。付费 API/GPU 开销为 0。
