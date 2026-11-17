# S05 小规模数据、评分与 B0 起始视角基线

日期：2026-11-17。状态：**两道开发题的 B0 技术 pilot 已运行；B1 随机 pilot 另见 [随机探索记录](S05_RANDOM_PILOT.md)。正式题集与主实验尚未完成**。

## 一个例子说明数据边界

题目 `fp1-door-white-002` 问“这间厨房的房门是白色的吗？”。起始帧面对冰箱，看不到足以判定房门颜色的画面；从起点执行一次 `RotateRight` 后，[参考帧](figures/door-reference.png)可见深棕色房门。因此真值是“否”，参考取证路径是一右转。用户随后确认了房门目标和这张颜色证据；标签复核状态已更新。

运行时 [公开题目](../data/dev_questions.json)只含 ID、题目、场景和起点姿态；[私有标签](../data/dev_labels.json)另存标准答案、参考动作、证据图片哈希和复核状态。[B0 脚本](../scripts/run_b0.py)只读取公开题目，检查重置后的自身姿态，然后把题目文字和初始 RGB 传给模型。它**不会执行动作、不会读取标签，也不会把姿态 metadata 送给模型**。[评分脚本](../scripts/score_answers.py)在预测保存后才读取私有标签。

另一个题目 `fp1-fridge-visible-001` 问是否有冰箱；起始帧已有明显冰箱。用户于本轮确认该帧可以作为证据。两题分别验证“起点有证据”与“起点缺证据”的流程，不代表计划中的 12 道开发题和 60 道测试题已经完成。

## 本机复现

在项目根目录运行，输出路径必须是新的空目录。依赖与模型下载步骤见 [环境记录](ENVIRONMENT.md)。

```bash
HF_HOME=.cache/huggingface HF_HUB_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
  ./.venv-vl/bin/python scripts/run_b0.py --output runs/s05-b0-new
./.venv-vl/bin/python scripts/score_answers.py \
  --predictions runs/s05-b0-new/predictions.json \
  --output runs/s05-b0-new/scores.json
./.venv-vl/bin/python -m unittest discover -s tests -v
```

最终实测输出保存在被 Git 忽略的 `runs/s05-b0-final/`：两张初始画面、`predictions.json`、原始 `scores.json`。用户确认第二题后只更新标签复核状态，另存重评分数为 `scores-reviewed.json`，保留原始评分文件。首次试跑另留在 `runs/s05-b0-20261117/`。模型为 S03/S04 相同的本地 2B 4-bit checkpoint；每题行动数为 0。最终两题回答分别是“是”和“是”，JSON 格式均通过。按真值“是”“否”计算：第一题正确得 1 分，第二题错误得 0 分；准确率 `(1+0)/2=0.5`，平均行动数 `0`，自定义行动效率分均值 `(1+0)/2=0.5`。此处的 0.5 **只是两题的流程校验数值**，不报告为策略效果或正式准确率。

第二题模型只看起点就答“是”，而起点画面不足以判断房门颜色；这条记录说明当前 B0 没有遵从“不确定”指令，不能推断错误的具体内部原因。右转取证能否让它改答“否”仍需后续对照运行。

评分器只接受事先列出的完整答案别名；“不确定”、格式失败或未解析答案均留在分母内且计错。对 20 次行动预算，单题效率为 `correct × (1 - actions_used / 40)`。例如 10 次行动后答对得 `0.75`；答错无论行动数均得 `0`。这是项目自定义辅助指标，不是 OpenEQA 官方分数。

## 验收边界与下一步

- 已检查：两题重置后自身姿态与题目记录一致；两张新 PNG 与模型预测保留；模型请求只含单张 RGB 和问题；离线评分与手算一致；7 项边界测试通过。
- 已由用户复核：第二题的房门目标和参考帧足以判“否”；标签状态为 `user_confirmed_door_target_and_color_2026-11-17`。
- 尚未完成：12 道开发题、60 道房间隔离测试题、正式 B1 对照与共同选帧协议、连续 10 题资源试跑、协议冻结和主实验。不能因为 B0 的两题结果挑选测试题。
