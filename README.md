# C6：主动具身问答项目工作区

暂定题目：**Look Before Answering: Question-Guided Exploration with Lightweight Semantic Memory**

在固定视觉语言模型、最多 20 次环境行动的条件下，比较不同探索策略回答室内问题的准确率与成本。主线为 AI2-THOR、自建测试集、问题引导搜索和轻量语义记忆。用户决定先按 VL 路线跑通；当前本机使用 Qwen3-VL-2B-Instruct 的 MLX 4-bit 版本做技术 pilot，正式实验模型尚未冻结，模型对比留到主线稳定以后。

## 从这里继续

1. 阅读 [AGENTS.md](AGENTS.md)，了解本工作区的协作约定。
2. 阅读 [PROGRESS.md](PROGRESS.md)，查看当前状态和唯一下一步。
3. 阅读 [MEMORY.md](MEMORY.md)，恢复已确认约束。
4. 阅读[本机环境与 S02/S03 实测](docs/ENVIRONMENT.md)和[分阶段编码顺序](docs/CODE_STAGES.md)，按 [PROGRESS.md](PROGRESS.md) 的当前下一步推进。完整路线在 [PLAN.md](PLAN.md)。

已完成 S02 仿真烟测、S03 单图问答和 S04 一题一行动闭环；S05 已运行两道开发题的 B0 起始视角基线与确定性评分 pilot。运行命令、证据和边界见 [ENVIRONMENT.md](docs/ENVIRONMENT.md)及 [S05 pilot](docs/S05_PILOT.md)。**正式题集与策略对比尚未完成，也未调用付费 API。**

## 文件索引

| 文件 | 作用 |
|---|---|
| [PLAN.md](PLAN.md) | 一个月完整计划、分工、预算、交付与降级路线 |
| [AGENTS.md](AGENTS.md) | 给后续编码助手读取的项目协作规则；不是运行中的 EQA agent |
| [MEMORY.md](MEMORY.md) | 精简、长期有效的项目约束与已确认事实；不是 EQA 模型的运行时记忆 |
| [PROGRESS.md](PROGRESS.md) | 当前状态、验收证据、阻塞与下一步 |
| [DECISIONS.md](DECISIONS.md) | 按时间追加的重要技术与实验决策 |
| [docs/EXPERIMENT_PROTOCOL.md](docs/EXPERIMENT_PROTOCOL.md) | 评测协议草案，正式实验前冻结 |
| [docs/FIRST_STEP.md](docs/FIRST_STEP.md) | 第一个可验收工作单元 |
| [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) | S01 本机审计与 S02–S04 实测 |
| [docs/CODE_STAGES.md](docs/CODE_STAGES.md) | 各个代码工作单元和通过条件 |
| [docs/S05_PILOT.md](docs/S05_PILOT.md) | 两道开发题、私有真值、B0 运行和手算评分 |
| [scripts/smoke_sim.py](scripts/smoke_sim.py) | S02 单房间、固定动作、重置烟测脚本 |
| [requirements-s02.txt](requirements-s02.txt) | S02 最小直接依赖 |
| [scripts/smoke_vl.py](scripts/smoke_vl.py) | S03 Qwen3-VL 单图问答与可核对的结果记录 |
| [requirements-s03.txt](requirements-s03.txt) | S03 本地 MLX 推理依赖 |
| [scripts/one_step_episode.py](scripts/one_step_episode.py) | S04 一次真实行动、两帧和本地回答的闭环 |
| [requirements-s04.txt](requirements-s04.txt) | S04 合并运行依赖 |
| [tests/test_one_step_episode.py](tests/test_one_step_episode.py) | S04 行动预算与输入隔离检查 |
| [data/dev_questions.json](data/dev_questions.json) | S05 运行时公开开发题 |
| [data/dev_labels.json](data/dev_labels.json) | S05 评分器私有真值与证据复核状态 |
| [scripts/run_b0.py](scripts/run_b0.py) | S05 起始视角 B0 实际运行 |
| [scripts/score_answers.py](scripts/score_answers.py) | S05 离线确定性评分 |
| [tests/test_s05_scoring.py](tests/test_s05_scoring.py) | S05 评分、预算与题目/真值隔离检查 |
| [docs/SESSION_TEMPLATE.md](docs/SESSION_TEMPLATE.md) | 后续工作／对话记录模板 |
| [logs/2026-11-10-planning.md](logs/2026-11-10-planning.md) | 本轮真实对话决策摘要 |

语义记忆算法是未来实现的研究模块，不能把这份项目 MEMORY.md 或评分真值交给实验 agent。

## 时间与资源

- 计划窗口：2026-11-10 至 2026-12-09，Asia/Shanghai。
- 团队：2–3 人，每人每周 8–12 小时。
- 当前资源：Apple M4 MacBook Air，16 GB 内存，S01 时约 190 GiB 可用磁盘；AI2-THOR 与 Qwen3-VL 已在 S04 同时运行一次，长期稳定性未验证。
- ¥300 为建议总预算上限，**尚未确认具体额度、供应商或消费操作**。
- 课程节点：12 月 17 日 17:00 海报，12 月 18 日展示，12 月 25 日 23:59 报告；以课程后续通知为准。

## 本地 Git 工作流

本目录是独立 Git 仓库，默认分支 `main`。不包含上层 NLP 作业，不配置远端、不自动上传。

```bash
git status --short
git log --oneline -5
git diff
```

一个验收单元对应一个小提交；提交前检查 diff、文件名单、敏感信息和验收记录。显式暂存相关文件，避免将数据、模型、密钥或历史作业意外纳入。首次初始化提交后可用 `git show --stat HEAD` 检查落盘内容。

大型数据、原始实验运行和回放放入忽略目录；正式实验仍须保存这些原始材料，在已跟踪的实验清单中记录路径、哈希、规模和备份位置。**Git 忽略不等于数据已有备份。**

后续恢复时可以直接说：

> 继续 c6_active_eqa 项目，先读 AGENTS.md、PROGRESS.md 和 MEMORY.md，完成当前工作单并更新日志。

## 来源

课程及技术资料的核对时间是 2026-11-10 的规划会话；本次落盘未重复联网核验。完整链接见 [PLAN.md](PLAN.md)。
