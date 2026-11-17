# OpenEQA · 在住宅里找证据再回答

本项目研究一个问题：在同样的 20 步预算内，Qwen3-VL 能否根据问题决定往哪里走，更快看到足以回答的证据？正式实验采用课程 C6 的路线 A。[课程要求](https://nlp-course-cuhksz.github.io/final-project.html)

## 场景、考题和评分

| 项目 | 配置 |
|---|---|
| 环境 | Habitat-Sim 加载 HM3D 住宅扫描。每步按相机位置和朝向渲染第一人称 RGB。|
| 题库 | 使用 OpenEQA 已发布的 HM3D 主动探索题。官方 JSON 中有 557 条 HM3D 问答，分属 63 个 episode history。保留原题、ID 和英文参考答案。|
| 模型 | 首轮使用本地 Qwen3-VL-2B-Instruct 的 MLX 4-bit 版本。兼容目标包括 Windows RTX 3060 6 GB。正式对照固定同一模型、量化和后端。|
| 公平比较 | 各组用相同题目和起点。每道题最多 20 个环境动作，记录每步画面、最终选帧、模型调用和耗时。|
| 评分计划 | 使用 OpenEQA LLM-Match 对开放回答和官方参考答案做语义评分，人工抽查评分并查看证据帧。另报平均动作数、失败原因。评分用的答案对行动模型隐藏。|

题库与场景需要匹配。每条题目的 episode_history 标识对应的住宅；同样的问题放到另一间房会失去原答案的依据。正式结果将公布实际使用的题目 ID、场景、起点、评分器和预算。[OpenEQA 数据说明](https://github.com/facebookresearch/open-eqa/blob/main/data/README.md)

## 实验组

| 组别 | 模型能看什么、何时回答 |
|---|---|
| 起始视角 | 只看出发点的一张照片，立即回答。|
| 随机探索 | 固定种子走动，在预算内收集画面，最后选帧回答。|
| 问题引导 | 根据问题和当前画面找线索，证据充分时回答。|
| 引导加记忆 | 额外记录看到了什么、在哪一步看到，供后续行动和回答使用。|

相同轨迹上比较等距抽帧与按画面变化选帧。相同策略下比较早停与走满预算。实验组的候选设计和成本见 [实验设计](docs/EXPERIMENT_DESIGN.md)。

## 本机运行和协作

从 [Habitat 配置与实测](docs/HABITAT_MAC.md) 开始。当前任务见 [项目进度](PROGRESS.md)，月度安排见 [计划](PLAN.md)。欢迎通过 issue 报告环境与复现问题，或提交包含输入、输出和验证方法的 pull request。

早期 AI2-THOR 厨房原型验证了本地模型看图、记录动作和选帧。两道开发题的结果只属于该原型。[历史闭环](docs/CLOSED_LOOP_WALKTHROUGH.md) · [随机探索记录](docs/S05_RANDOM_PILOT.md)
