# 2026-11-10 · S04 一题一行动最小闭环

> 工作／对话摘要，非逐字稿。时间：Asia/Shanghai。

## 用户本轮要求与补充

- 用户在 S03 后说“ok继续”，按 PROGRESS 的唯一下一步执行 S04。
- 延续小工作单、本地免费试跑、模型输入不得含评分真值的已有约定。

## 本轮唯一目标

- 在同一个 `FloorPlan1` episode 中取得首帧、执行一次受限行动、取得次帧，并让本地 Qwen3-VL 根据实际观察回答一个问题。验证预算、输入隔离和同时运行资源。

## 实际执行

- 在 `.venv-vl` 中安装 `ai2thor==5.0.0`；新增 `requirements-s04.txt`、`scripts/one_step_episode.py` 和两项边界测试。
- 固定问题“这两张画面中是否看到了冰箱？”，动作 `RotateRight`；这只是脚本动作，不是模型选动作。行动预算 1 次，在 `controller.step` 前扣减，即使行动失败也计数。
- 模型输入由白名单建立：两张 RGB、问题、前次动作名及成功布尔值、行动预算。没有向模型传 `objects`、完整 metadata、评分真值或项目 MEMORY.md。
- 首次运行保存 `runs/s04-one-step/episode.json`，模型答“是、证据帧 1”，但省略第三个证据文本字段，格式检查返回非零。随后将 S04 最小输出契约收窄为答案和证据帧号，保留失败记录；重跑结果在 `runs/s04-one-step-verified/episode.json`、`frame1.png`、`frame2.png`。
- 最终运行输出 `status=completed`，动作成功，模型答 `{"answer":"是","evidence_frame":1}`。人工查看第 1 帧正对冰箱，第 2 帧主要是门；证据帧编号合理。Unity 在模型推理前后均存活。

## 验证边界

- `PYTHONPYCACHEPREFIX=.cache/pycache ./.venv-vl/bin/python -m unittest discover -s tests -p 'test_one_step_episode.py' -v` 两项测试通过：预算耗尽拒绝第二次行动、非法动作被拒绝；伪造隐藏对象／答案没有进入模型输入。
- 最终清理前总时长 4.873 秒（Unity 启动 2.980、取图及行动 0.020、模型加载 0.883、生成 0.989）；MLX 峰值内存 2.277 GB。Unity 取样 RSS 约 633/367 MB，两次取样不是峰值，不能与 MLX 内存直接相加。
- 单题、一次行动通过不证明策略能力、正式评分准确率或长时间运行稳定。输出目录 `runs/` 和本地模型均被 Git 忽略。

## 决策与理解检查

- D011 记录固定动作与两字段输出契约的暂定边界；问题引导探索留待后续工作单。
- 一个实际例子：observation 是冰箱图和右转后的门图；action 是 `RotateRight`；feedback 是动作成功；answer 是“是”，来源是第 1 帧。评分真值尚未进入运行时模型输入，下轮 S05 才建立评分器。

## 费用与版本

- 付费 API/GPU 开销：0。
- 父提交：`e93a31b`。本轮提交用 `git log -- logs/2026-11-10-s04-one-step-episode.md` 查询。

## 下一步

- 唯一下一目标：S05 最小数据与确定性评分，先 1–2 个可手算样例和起始视角基线，再扩展正式题集。
