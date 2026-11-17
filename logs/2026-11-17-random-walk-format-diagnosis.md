# 随机轨迹与回答格式复核

用户问 B1 格式失败是否随机，以及为什么 6 次前进中 5 次碰撞而画面几乎不动。本轮检查原始模型输出和 20 步位姿，并另存一条更能脱困的开发轨迹。

原轨迹 seed 17 的动作完全可复现。第 3 步前进 0.25 米，第 4、5 步继续撞向同一侧障碍，虽有 0.1865 和 0.0354 米的滑动；第 6 步左转 10°后，第 8 步前进只移动 0.0082 米并碰撞；第 9、10 步右转和第 11 步左转基本抵消。第 14、16 步继续向初始方向尝试前进并碰撞。8 次俯仰只改变相机朝向。故有 6 次水平转向，却仍主要朝着障碍前进。此结果由独立均匀采样、10° 转角和起点位置共同造成。仅一条轨迹不能估计发生概率。

B1 原始推理文本是 `unknown`，JSON 解析器因此返回 None。模型表达了证据不足，但没有生成题设要求的 `{"answer":"unknown","frame":0}`。原始结果的 `valid=false` 正确表示格式不合规，不能据此说语义答案错误。模型设置 temperature=0、seed=0。这次不同轨迹的 B1 四图输入再次得到纯文本 `unknown`，说明现象并非本次运行独有；仍不能证明所有输入都会这样。新解析记录独立的 `normalized_answer`，原始文本及 `valid` 保留。`unknown` 没有可引用证据帧，记为 null。

另以 `--policy collision_aware` 运行同一题、同一起点、seed 17、20 次动作。无碰撞时从前进、前进、左转、右转四选项抽取；碰撞后下一步随机左/右转 90°。这是一项新的开发对照，动作集及转角均改变，不能与旧 B1 做单变量策略因果解释。新轨迹 8 次前进、12 次转向、2 次碰撞，最远距起点 1.319 米；旧轨迹对应 6 次前进、6 次转向、8 次俯仰、5 次碰撞、0.446 米。21 张 RGB 和四张选帧保存在 `runs/habitat-washer-recovery-20/`，全轨迹回放已人工查看。新轨迹看到客厅、楼梯、窗等，仍未取得能判定洗衣机上方物体的画面。B0 是 JSON unknown，B1 又是纯文本 unknown。两轮 B1 四图帧号均为 0、7、13、20，最终没有答出官方答案 The dryer。

运行命令如下，输出目录须使用新名称。

```bash
runs/habitat-env/bin/python scripts/habitat_paired_pilot.py render --scene data/raw/route-a/example/GLAQ4DNUx5U.basis.glb --run runs/habitat-washer-recovery-replay --policy collision_aware
HF_HUB_OFFLINE=1 .venv-vl/bin/python scripts/habitat_paired_pilot.py answer --run runs/habitat-washer-recovery-replay --question-id b70465b8-53a3-436f-b12f-2d8cdf8f1856
```

针对纯文本拒答、合法 JSON 和越界帧号新增聚焦测试。下一工作单应登记更多匹配的住宅与题目，并在选定开发题上检验取证和四图保留。
