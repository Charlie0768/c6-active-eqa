# 2026-11-10 · S03 Qwen3-VL 单图烟测

> 工作／对话摘要，非逐字稿。时间：Asia/Shanghai。

## 用户本轮要求与补充

- 用户在 S02 完成后要求“好的 执行下一步”，即 PROGRESS 中的 S03。
- 延续先按 VL 路线、小工作单验收和避免高价模型费用的已有决定。

## 本轮唯一目标

- 让 Qwen3-VL 真正读取 S02 的一张 RGB 画面并作简短结构化问答；记录模型和图像身份、原始/解析输出、耗时、资源及费用。

## 实际执行

- 依据公开 [MLX-VLM 文档](https://github.com/Neywa-Labs/mlx-vlm/blob/main/README.md)和[模型仓库](https://huggingface.co/mlx-community/Qwen3-VL-2B-Instruct-4bit)，选择本机 MLX 4-bit 技术试跑。用现有 Python 3.11.14 建 `.venv-vl`，安装 `mlx-vlm==0.7.6`；新增 `requirements-s03.txt`、`scripts/smoke_vl.py`，更新 `.gitignore`。
- 用 Hugging Face API 查到公开仓库修订版 `9c4f5209e57b31f4b9dfba735de3fb983739c9cc`、16 个文件共 1,798,023,774 字节；固定修订版下载到 Git 忽略的 `models/qwen3-vl-2b-instruct-4bit/`。本机模型目录约 1.7 GiB、隔离环境约 815 MiB；未触发约 5 GB 新增文件停止线。
- 只把 `runs/smoke-final/run1_step00.png` 和固定问题“能否看到冰箱”交给模型；脚本验证权重 SHA-256、图片 SHA-256，以及格式化提示词恰有一个图像占位符。未读取仿真 metadata、评分真值或项目 MEMORY.md 作为模型输入。
- 首次实际推理答 `是`，但输出包在 Markdown JSON 围栏中，严格解析退出非零。随后只增加围栏规范化，保留原始输出，重跑后通过。最终验收记录为 `runs/s03-one-image-accepted/result.json`，其原文、解析 JSON、版本、哈希、136 输入/28 输出 token、耗时和内存均已保存。

## 验证边界

- 最终输出：`{"answer":"是","evidence":"冰箱在画面中央，清晰可见"}`；与 S02 首帧可人工核对，`valid_answer_json=true`，`json_code_fence_removed=true`。最终模型加载 0.901 秒、生成 0.984 秒、MLX 峰值内存 2.039 GB。初次生成用时 3.529 秒；这些是同机单图烟测，不是稳态吞吐基准。
- 结果图片 SHA-256 与 S02 轨迹首帧相同，模型权重 SHA-256 与脚本固定值相同，输入 token 和输出 token 非零。单图输出不代表多题准确率；社区 4-bit checkpoint 不等于原始未量化模型。
- 默认沙箱不能访问 Metal GPU；允许本机 GPU 的受控运行环境可推理。尚未验证 Unity 与 MLX 同时运行、连续 episode、动作选择和正式评分。

## 决策与理解检查

- D010 记录 S03 选用本机社区量化版的技术试跑理由和暂定地位；正式模型未冻结。
- 下次用这张冰箱图解释 observation（图像）、action（可执行动作）、feedback（动作结果）和 answer（模型回答）的区别，并展示评分真值为何要隔离。

## 费用与版本

- 付费 API/GPU 开销：0；模型和依赖下载以及本机计算未计货币费用。
- 父提交：`3c8d6fc`。本轮提交用 `git log -- logs/2026-11-10-s03-vl-single-image.md` 查询。

## 下一步

- 唯一下一目标：S04，一题一行动的最小闭环；先定义模型可见字段和动作预算，实际检查 Unity 与 MLX 同时运行资源，再决定是否分进程顺序运行。
