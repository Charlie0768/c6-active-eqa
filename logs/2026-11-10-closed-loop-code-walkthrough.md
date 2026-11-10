# 2026-11-10 · S02–S04 闭环代码导读与注释

> 工作／对话摘要，不是逐字聊天记录。时间为 Asia/Shanghai。

## 用户本轮要求与补充

- 用户要求列出闭环所有代码文件并解释职责，在代码中加详细注释，按流程讲解，并说明 VL 模型、环境和图片是否在本地，以及当前“显存”能否运行正式测试。
- 本轮授权范围是代码注释、导读与核查；未要求启动正式批量实验或购买资源。

## 本轮唯一目标

- 输入：已完成的 S02、S03、S04 脚本、依赖清单和本机验收记录。
- 产物：4 个 Python 文件和 3 个依赖清单的中文注释、`docs/CLOSED_LOOP_WALKTHROUGH.md`、进度记录。
- 验收条件：不改变运行逻辑；可按文件和数据流理解；本机/内存结论有记录支持。

## 实际执行

- 对三个脚本和一个边界测试补充模块、函数及关键步骤的中文注释；依赖清单说明各自适用阶段。
- 复核 `runs/s04-one-step-verified/episode.json`：一次固定右转、两帧、本地模型回答“是、证据帧 1”，MLX 峰值 2.277 GB，Unity 在模型前后存活。
- 本机复核 `system_profiler`：Apple M4 MacBook Air、16 GB 内存。目录当前量级：模型 1.7 GiB、`.venv-vl` 851 MiB、`.venv` 195 MiB、`~/.ai2thor` 1.0 GiB。
- 导读说明 AI2-THOR 的本机 Unity 预制场景渲染与 Pillow PNG 保存，不将其误称为自行建模；模型本地 MLX 推理，已执行阶段无付费调用。

## 验证边界

- 4 个 Python 文件去掉 docstring 后的可执行 AST 与父提交逐一相同；3 个依赖清单只改注释。`./.venv-vl/bin/python -m unittest discover -s tests -v` 的 2 项测试通过，`git diff --check` 通过。
- 没有重新运行 Unity/MLX；S04 的真实运行证据来自前一工作单保留的本机文件。
- 只证实单次 2B 4-bit 两帧闭环；没有做 20 步、连续 10 题、完整正式题集或 4B 压测。

## 决策与理解检查

- 没有新的模型或实验协议决定；S05 仍是下一工作单。
- 用户的“显存”在这台 Apple M4 上应按 CPU/GPU 共享的统一内存理解；MLX 峰值不是整机峰值。

## 费用与版本

- 本轮新增付费开销：0；项目累计付费调用：0。
- 父提交：`b6dc0c8 feat: run one-action embodied QA episode`。
- 本轮提交使用 `git log -- logs/2026-11-10-closed-loop-code-walkthrough.md` 查询。

## 下一步

- 唯一下一目标：S05 小规模题目字段、可人工核对真值、确定性评分与起始视角基线。正式批量前另做顺序多 episode 资源门槛试跑。
