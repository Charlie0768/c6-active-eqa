# 2026-11-10 · 先按 VL 路线试跑与 S01 资源审计

用户最新决定：“先按 VL 的来试试，先跑通，之后如果需要再换一下模型试试”，并询问代码应分部分还是一次性生成。

解释为恢复原计划的 Qwen3-VL 候选，先建立小规模可运行闭环；之前选择通用廉价 API 仅为历史建议。用户没有要求立即生成全部实现。

本轮只读实测：Apple M4 MacBook Air、16 GB 内存、macOS 27.0.1、arm64，当前目录约 190 GiB 可用；系统 Python 3.9.6、Conda Python 3.13.5。两者均未发现 ai2thor、torch、transformers。`sysctl` 内存查询被拒，随后 `system_profiler` 返回结果。未安装任何包、下载模型或运行实验。

官方资料复核：[AI2-THOR 安装与首次下载](https://ai2thor.allenai.org/ithor/documentation/)和 [Qwen3-VL-2B-Instruct 模型卡](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)。仅核对文档，不推断本机兼容或模型质量。

新增 D009；更新 PLAN v1.3、README、MEMORY、PROGRESS，并记录 ENVIRONMENT 与 CODE_STAGES。推荐分阶段实现，下一代码单元 S02 是单房间仿真烟测。费用与模型规格仍待实测，未开始 API 调用、付费或 GPU 租用。
