# 2026-11-10 · S02 单房间仿真烟测

> 工作／对话摘要，非逐字稿。时间：Asia/Shanghai。

## 用户本轮要求与补充

- 用户要求“ok执行s02”，沿用此前“先 VL 路线跑通、分部分生成代码”的决定。
- 本轮没有授权付费模型调用或扩大到 S03/S04。

## 本轮唯一目标

- 在本机实际启动 AI2-THOR 单一房间，保存 RGB、固定动作反馈，并重置重复一次；产出可核对的轨迹与本地 Git 提交。

## 实际执行

- 创建被 Git 忽略的 `.venv`，安装 `ai2thor==5.0.0`、`pillow==11.3.0`、`numpy==2.0.2` 与解析出的依赖；新增 `requirements-s02.txt` 和 `scripts/smoke_sim.py`。
- 命令：`./.venv/bin/python scripts/smoke_sim.py --scene FloorPlan1 --output runs/smoke-final`。首次运行下载了约 775 MB 的官方 `OSXIntel64` Unity 构建到 `~/.ai2thor`。当前 Python 是 macOS arm64 的 3.9.6。
- 两轮各从同一房间开始，执行 `RotateRight`、`MoveAhead`、`RotateLeft`、`LookDown`、`LookUp`。最终输出为 `runs/smoke-final/summary.json`、`trace.jsonl` 和 12 张 300×300 PNG；目录被 Git 忽略，仅保留在本机。
- 逐条检查了 12 条轨迹、步骤顺序、12 张可打开的 PNG 及各自 SHA-256；对应动作反馈、agent 位姿和帧尺寸在 reset 前后相同，两轮均 5/5 动作成功。人工查看首帧可见冰箱及厨房局部。
- 早期沙箱执行因无法访问构建地址报 “no build exists”，联网重试后开始下载；再次沙箱执行因无法写 `~/.ai2thor` 锁文件失败，允许该缓存写入后最终脚本运行成功。这些错误是执行权限边界，不能当成平台不兼容。

## 验证边界

- `runs/smoke-final/summary.json` 的 `all_states_match_across_reset=true`，`all_pngs_match_exactly=false`。最终首帧跨 reset 平均绝对像素差约 22.38/255、最大单通道差 39；截图肉眼仍为同一视角。脚本把状态重放和像素一致性分开记录，并在状态不一致时以非零退出。
- S02 确认了当前 Mac 可以输出 AI2-THOR 帧和动作反馈。尚未运行 Qwen3-VL、主问题集、评分或同时运行资源测试；没有声称研究方法有效。
- `requirements-s02.txt` 固定直接依赖，传递依赖的解析版本没有全部锁定；正式实验前需固定完整环境。

## 决策与理解检查

- 没有新增研究方案决策；把“图像哈希不作为 reset 验收”写入 `MEMORY.md` 和 `docs/ENVIRONMENT.md`。
- 下次用真实冰箱视角解释“观察帧（observation）—动作（action）—反馈（feedback）—重置（reset）”，并在 S03 里只把图像传给 VL 模型。

## 费用与版本

- 付费 API/GPU 开销：0；下载安装与本机计算未计货币费用。
- 父提交：`72edd6b`。本轮提交用 `git log -- logs/2026-11-10-s02-simulator-smoke.md` 查询。

## 下一步

- 唯一下一目标：S03，用 S02 的一张真实 RGB 做 Qwen3-VL 单图烟测，记录实际模型版本、输入、输出、时延和资源／费用；先定明确的免费或低成本执行方式与停止条件。
