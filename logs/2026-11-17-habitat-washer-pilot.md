# 洗衣机原题的 Habitat B0 与 20 步 B1

本机 M4，离线 Qwen3-VL-2B-Instruct MLX 4-bit，960×540。当前一题用于开发。[课程 C6](https://nlp-course-cuhksz.github.io/final-project.html) 的第一周里程碑列出 60 题。本项目计划额外用 12 题开发，再用 60 题测试，按住宅隔离。当前仅有一个能匹配题库的住宅、11 道可跑原题；正式 60 题尚未登记。

## 复现

从项目根目录执行，使用一个新的输出目录。第一条命令生成 21 张图和 trace.json。第二条只给模型问题与已选 RGB，写入以官方问题 ID 命名的结果文件。B0/B1 共用一个起始文件。用 seed 17 抽样可走点，起点与早期实测位姿一致；这是工程起点。每次动作前扣预算，转向与俯仰为 10 度，前进为 0.25 米。

```bash
runs/habitat-env/bin/python scripts/habitat_paired_pilot.py render --scene data/raw/route-a/example/GLAQ4DNUx5U.basis.glb --run runs/habitat-washer-replay
HF_HUB_OFFLINE=1 .venv-vl/bin/python scripts/habitat_paired_pilot.py answer --run runs/habitat-washer-replay --question-id b70465b8-53a3-436f-b12f-2d8cdf8f1856
```

## 实际观测

- 题目问洗衣机上面有什么，官方参考为 The dryer。住宅 GLAQ4DNUx5U。首次运行保存在 runs/habitat-washer-20/。
- B0 看第 0 帧，原始输出为 `{"answer": "unknown", "frame": 0}`。模型推理耗时 1.920 秒，MLX 峰值 2.585 GB。
- B1 随机种子为 17，走满 20 步，最终看第 0、7、13、20 帧。原始输出为纯文本 `unknown`，格式校验失败，未引用图片。推理耗时 5.444 秒，MLX 峰值 2.798 GB。两组均未给出参考答案。没有运行付费评审。
- 6 次前进、6 次水平转向、8 次俯仰，Habitat 返回 5 次碰撞，最远仅距起点 0.446 米。回放逐格可见石墙与墙上开口，未发现显示洗衣机及其上方物体的帧，归类为探索未取证。
- 已重开 21 张 PNG 并核验哈希、RGB 和尺寸，核对随机动作顺序、第 21 次动作预算拒绝、与早期起点的位置及四元数一致。现有 11 项测试通过。轨迹 SHA-256 为 5b2c347cbde354e63ecd71f916808bccd3732f0ba0d29355a263c1845a5e8e30。本地 full-replay.jpg 为全轨迹拼图，model-inputs.jpg 为最终四图。
