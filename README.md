# Look Before Answering · 主动具身问答

助手站在虚拟厨房里，面前是一台冰箱。有人问“这间厨房的房门是白色的吗？”它可以转头、前进、观察，最后给出答案。这个课程项目研究同一个视觉语言模型怎样在最多 20 个动作内找到证据，并据此回答问题。

## 1. 环境、考题与评分

| 项目 | 当前可复现的设置 |
|---|---|
| 场景 | AI2-THOR 5.0.0 的 `FloorPlan1` 厨房。每题从记录的同一起点和朝向开始，每步返回一张 300 × 300 的第一人称 RGB 图。 |
| 考题 | 两道自建中文开发题，均已人工核对。冰箱题的答案为“是”，起始帧就能判断。房门白色题的答案为“否”，从起点右转可看见深棕色房门。[题目与起点](data/dev_questions.json) · [评分标签](data/dev_labels.json) |
| 模型 | 本地 `mlx-community/Qwen3-VL-2B-Instruct-4bit`，即 Qwen3-VL-2B-Instruct 的 MLX 社区量化版。Python 3.11、MLX-VLM 0.7.6，已在 Apple M4、16 GB 统一内存上实跑。生成参数为 temperature 0、seed 0、最多 64 个输出 token。 |
| 动作与预算 | 可前进、左转、右转、抬头、低头。失败动作也计一次。B1 的试验种子为 17，每题尝试 20 次，保存起点与每次尝试后的画面，共 21 张。 |
| 模型能看到什么 | 回答时只获得问题与所选图片。答案、人工参考路径和仿真器中的物体清单留给离线评分与核查。 |

**主指标是准确率。** 每题按 ID 对齐，解析模型输出并与人工答案比较。弃答“不确定”和格式错误均计错。另报平均动作数，以及项目自定义的效率分：答对时得 `1 − 动作数 / 40`，答错得 0，再取所有题的平均。例如答对同一题，原地回答得 1，走满 20 步得 0.5。[评分实现](scripts/score_answers.py)

题型设计参考 OpenEQA 对“回看历史”和“主动探索”的区分。当前是非题使用确定性评分。OpenEQA 的 LLM-Match 则适合需要判断措辞是否等价的开放答案。探索与停止策略参考 Explore until Confident。本项目选择 AI2-THOR 搭建交互环境，Habitat 3.0 是另一种平台选择。[OpenEQA](https://open-eqa.github.io/) · [Explore until Confident](https://arxiv.org/abs/2403.15941) · [AI2-THOR](https://ai2thor.allenai.org/) · [Habitat 3.0](https://aihabitat.org/habitat3/) · [Qwen3-VL](https://github.com/QwenLM/Qwen3-VL)

## 2. 要比较的实验

研究问题有两个：**根据问题决定下一步往哪走，能否更快取得足够的证据？记住已经看过的内容，能否进一步减少重复探索？**

| 组别 | 如何行动、如何回答 | 状态 |
|---|---|---|
| B0 起始视角 | 站在起点，给模型一张图，直接回答。衡量单凭起点能做对多少。 | 两题已运行 |
| B1 随机探索 | 从五个动作中等概率抽样，走完再回答。当前从 21 张图里按时间选第 0、7、13、20 帧。 | 两题已运行 |
| B2 问题引导 | 每步结合问题和当前画面选动作，线索不足就继续观察，取得足够证据时停止。 | 计划实现 |
| B3 问题引导加记忆 | 在 B2 上增加带来源帧号的观察笔记，供后续行动和最终回答使用。 | 计划实现 |

正式比较计划用 12 道开发题确定规则，再用房间隔离的 60 道测试题评估。各组固定模型、起点与评分口径，主动组共用最终选帧规则。消融分三步：先在同一轨迹和同样四张图的额度下比较选帧方法，再让 B2 分别早停和走满 20 步，最后比较 B2 与 B3 的记忆增量。除答案与动作外，还要记录证据是否真正进入模型、模型调用数、token 和耗时。[实验设计](docs/EXPERIMENT_DESIGN.md)

## 3. 已跑出的两题结果

| 条件 | 答对 | 平均动作数 | 平均效率分 |
|---|---:|---:|---:|
| B0 起始视角 | 1/2 | 0 | 0.50 |
| B1 随机探索 | 2/2 | 20 | 0.50 |

房门出现在 B1 轨迹的第 10 步，最终送给模型的四帧却都没清楚拍到它。尽管这一题答对，现有输入无法支持“模型看到了门的颜色”这一解释。下一项实验会直接比较不同选帧方法保留证据的比例。[第 10 步原图](docs/figures/door-step10.png) · [模型实际收到的四帧](docs/figures/door-selected.png) · [运行记录](docs/S05_RANDOM_PILOT.md)

## 4. 本地复现

下列命令适用于带 Metal GPU 的 Apple Silicon Mac。在仓库根目录运行。首次运行需要联网下载固定版本的权重和 AI2-THOR 的 Unity 程序，之后可用本地权重推理。每次试验请给新的输出目录。

```bash
git clone https://github.com/Charlie0768/c6-active-eqa.git
cd c6-active-eqa
python3.11 -m venv .venv-vl
source .venv-vl/bin/activate
python -m pip install -r requirements-s04.txt
python -c "from huggingface_hub import snapshot_download; snapshot_download('mlx-community/Qwen3-VL-2B-Instruct-4bit', revision='9c4f5209e57b31f4b9dfba735de3fb983739c9cc', local_dir='models/qwen3-vl-2b-instruct-4bit')"
python -m unittest discover -s tests -v
export HF_HUB_OFFLINE=1
python scripts/run_b0.py --output runs/demo-b0
python scripts/run_b1_random.py --seed 17 --budget 20 --output runs/demo-b1
python scripts/score_answers.py --predictions runs/demo-b0/predictions.json --output runs/demo-b0/scores.json
python scripts/score_answers.py --predictions runs/demo-b1/predictions.json --output runs/demo-b1/scores.json
```

每个输出目录的 `predictions.json` 保存模型原始回答和实际输入，`scores.json` 保存逐题分数。完整轨迹、模型权重和虚拟环境保存在运行者本机。仓库附带上述房门案例的小型图片，便于直接核查结果。[本机环境记录](docs/ENVIRONMENT.md) · [代码导读](docs/CLOSED_LOOP_WALKTHROUGH.md)

## 5. 参与协作

欢迎通过 Issue 提出有清楚视觉证据的题目、报告复现问题，或 fork 后提交 Pull Request。贡献题目时请描述房间、起点、题目、参考动作和足以判断的证据帧。改动探索策略时请注明模型版本、种子、动作预算、实际选帧，以及同题对照结果。当前工作与待办见 [项目进度](PROGRESS.md)。
