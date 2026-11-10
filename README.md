# C6：主动具身问答项目工作区

暂定题目：**Look Before Answering: Question-Guided Exploration with Lightweight Semantic Memory**

在固定视觉语言模型、最多 20 次环境行动的条件下，比较不同探索策略回答室内问题的准确率与成本。主线为 AI2-THOR、自建测试集、问题引导搜索和轻量语义记忆。用户最新决定先按原先的 VL 路线跑通：以 Qwen3-VL 为首轮候选，具体 2B／4B 规格及本地或低成本服务方式经过单图测试确定；模型对比留到主线稳定以后。

## 从这里继续

1. 阅读 [AGENTS.md](AGENTS.md)，了解本工作区的协作约定。
2. 阅读 [PROGRESS.md](PROGRESS.md)，查看当前状态和唯一下一步。
3. 阅读 [MEMORY.md](MEMORY.md)，恢复已确认约束。
4. 阅读[本机环境与 S02 实测](docs/ENVIRONMENT.md)和[分阶段编码顺序](docs/CODE_STAGES.md)，按 [PROGRESS.md](PROGRESS.md) 的当前下一步推进 S03。完整路线在 [PLAN.md](PLAN.md)。

已完成 S02 本机仿真烟测：AI2-THOR 在当前 Mac 上输出真实 RGB、动作反馈和重置轨迹。运行命令、证据和像素复现边界见 [ENVIRONMENT.md](docs/ENVIRONMENT.md)。**尚未下载／运行 Qwen3-VL、调用付费 API 或运行 EQA 主实验。**

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
| [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) | S01 本机审计与 S02 仿真实测 |
| [docs/CODE_STAGES.md](docs/CODE_STAGES.md) | 各个代码工作单元和通过条件 |
| [scripts/smoke_sim.py](scripts/smoke_sim.py) | S02 单房间、固定动作、重置烟测脚本 |
| [requirements-s02.txt](requirements-s02.txt) | S02 最小直接依赖 |
| [docs/SESSION_TEMPLATE.md](docs/SESSION_TEMPLATE.md) | 后续工作／对话记录模板 |
| [logs/2026-11-10-planning.md](logs/2026-11-10-planning.md) | 本轮真实对话决策摘要 |

语义记忆算法是未来实现的研究模块，不能把这份项目 MEMORY.md 或评分真值交给实验 agent。

## 时间与资源

- 计划窗口：2026-11-10 至 2026-12-09，Asia/Shanghai。
- 团队：2–3 人，每人每周 8–12 小时。
- 当前资源：Apple M4 MacBook Air，16 GB 内存，S01 时约 190 GiB 可用磁盘；AI2-THOR 单独运行已验证，Qwen3-VL 及同时运行资源未验证。
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
