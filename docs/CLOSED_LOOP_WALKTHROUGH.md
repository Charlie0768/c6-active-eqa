# S02–S04 闭环代码导读

本文对应 2026-11-10 的技术烟测，供按文件阅读和复现。这里的“闭环”指**场景给出画面 → 脚本执行一次动作 → 取得新画面 → 本地 VL 模型答题 → 保存记录**。动作仍由脚本固定，尚不是模型自主探索，也没有正式题集与评分。

## 文件导航

| 文件 | 阶段和职责 | 主要输入 → 输出 |
|---|---|---|
| [`scripts/smoke_sim.py`](../scripts/smoke_sim.py) | S02：AI2-THOR 启动、固定动作、重置比较 | `FloorPlan1` → 12 张 PNG、`trace.jsonl`、`summary.json` |
| [`scripts/smoke_vl.py`](../scripts/smoke_vl.py) | S03：本地模型单图问答；检查权重版本和 JSON 格式 | S02 首帧 + 本地权重 → `result.json` |
| [`scripts/one_step_episode.py`](../scripts/one_step_episode.py) | S04：保持 Unity 运行，取前后两帧，本地推理并记录资源 | 场景 + 本地权重 → `frame1.png`、`frame2.png`、`episode.json` |
| [`tests/test_one_step_episode.py`](../tests/test_one_step_episode.py) | 无需启动 Unity/MLX 的边界测试：行动预算与 metadata 隔离 | 伪造输入 → 测试通过/失败 |
| [`requirements-s02.txt`](../requirements-s02.txt) | S02 仿真、图片和像素差异依赖版本 | 安装到 `.venv` |
| [`requirements-s03.txt`](../requirements-s03.txt) | S03 本地 VL 推理依赖版本 | 安装到 `.venv-vl` |
| [`requirements-s04.txt`](../requirements-s04.txt) | 在 S03 环境中增加 AI2-THOR，支持 S04 同进程运行 | 安装到 `.venv-vl` |

`AGENTS.md`、`MEMORY.md` 和 `PROGRESS.md` 是项目协作、长期上下文和进度文件，不是运行时 agent 的策略代码。`.gitignore` 让模型权重、虚拟环境、帧和运行记录留在本机而不进入 Git。

## 按执行顺序理解

1. **准备环境和资源。** S02 的 `.venv` 使用 Python 3.9；S03/S04 的 `.venv-vl` 使用 Python 3.11。AI2-THOR 首次启动时下载官方 Unity 场景程序到 `~/.ai2thor`。公开的社区 4-bit Qwen3-VL-2B-Instruct checkpoint 下载到项目内 `models/qwen3-vl-2b-instruct-4bit/`；脚本读取本地路径并核验权重 SHA-256，不调用在线模型 API。具体命令见 [`ENVIRONMENT.md`](ENVIRONMENT.md)。
2. **先单独验仿真（S02）。** `Controller(scene="FloorPlan1", width=300, height=300)` 启动本机 Unity，`last_event.frame` 是初始第一人称 RGB。脚本执行 `RotateRight → MoveAhead → RotateLeft → LookDown → LookUp`，再 reset 重做一轮。每个 event 的 RGB 数组经 Pillow 保存成 300×300 PNG；轨迹记录动作反馈和 agent 自身位姿。比较重置后的动作/位姿是否一致，同时记录像素差；不把 PNG 字节完全相同当作通过条件。
3. **再单独验模型（S03）。** 用 S02 的首帧问“能否看到冰箱”。`load()` 加载本地 MLX 模型，`apply_chat_template(..., num_images=1)` 放入一个图像占位符，`generate()` 接收图片路径。保留原始回答、解析 JSON、检查字段及证据文字，输出耗时与 MLX 报告的峰值内存。它没有访问仿真 metadata。
4. **最后连接（S04）。** 在同一 Python 进程创建 AI2-THOR `Controller`，保存 `frame1.png`；在执行前扣除 1/1 行动预算，固定执行 `RotateRight`，只从 metadata 提取 `lastActionSuccess`，保存 `frame2.png`。构造包含问题、两张已观察图片、动作成功标志和预算的白名单清单。`make_prompt()` 把文字字段组织为提示词；两张图片依清单顺序传给 `generate()`。清单中的 SHA-256 与尺寸仅用于记录，模型文字提示词不包含这些值。最后解析 `answer` 与 `evidence_frame`，写 `episode.json`，并在 `finally` 中关闭 Unity。
5. **核对真实例子。** `FloorPlan1` 首帧看到冰箱，右转后的第二帧主要看到门。模型回答 `{"answer":"是","evidence_frame":1}`；人工查看图片可核对证据确实来自第一帧。这只验证接口与这个例子，不代表模型在题集上的准确率。

## 图片和本地运行到底是什么

本项目**没有手工建模或用生成模型合成这两张场景图**。`FloorPlan1` 是 AI2-THOR 已提供的室内 3D 场景；本机 Unity 按 agent 的位置和朝向渲染第一人称画面，Python 从 `event.frame` 获取 RGB 像素并保存为 PNG。场景资源与 Unity 程序由 AI2-THOR 获取并缓存在本机。VL 模型权重也在本机，MLX 使用 Apple 芯片运行推理。已执行的 S02–S04 没有云 GPU 或付费 API 调用。

当前本地位置与量级（会随安装更新而变化）：模型目录约 1.7 GiB，`.venv-vl` 约 851 MiB，`.venv` 约 195 MiB，`~/.ai2thor` 约 1.0 GiB；`runs/` 保存本机生成的帧与 JSON。`runs/smoke-final/`、`runs/s03-one-image-accepted/`、`runs/s04-one-step-verified/` 是对应验收记录。上述大文件和生成结果都被 Git 忽略。

## 16 GB 内存与正式测试

本机为 Apple M4 MacBook Air、16 GB **统一内存**，CPU 和 GPU 共享它，不存在可独立相加的“16 GB 内存 + 一块固定显存”。在一次已完成的 S04 闭环里，MLX 报告峰值 2.277 GB；Unity 在模型前后均存活，取样 RSS 分别约 633 MB/367 MB；清理前总计 4.873 秒。这说明**2B 4-bit 模型加一个场景的单次两帧测试已能在本机运行**。MLX 峰值不是整机内存峰值，Unity 的两个 RSS 读数也不是生命周期峰值；不能据此保证 20 步、多图历史、长批量或 4B 模型都能稳定运行。

下一阶段可先做单实例、顺序执行的资源门槛试跑：保持固定 2B 4-bit 权重，逐步增加到计划的 20 次动作上限，再连续运行 10 个 episode；每次记录图片数量、提示词 token、MLX 峰值、进程和 Unity RSS、整机内存压力/交换空间、耗时与失败。内存压力持续红色、交换空间持续增长、进程被杀或模型/Unity 报内存错误时停止，不进入正式批量。若计划累计多帧历史，还需限定送入模型的帧数或压缩已观察证据；当前 S04 每次只传两张图。此试跑尚未执行，因此“正式测试可在本机全量完成”仍是待验证判断。
