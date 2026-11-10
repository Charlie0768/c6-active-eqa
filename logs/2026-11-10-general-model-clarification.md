# 2026-11-10 · 通用模型意图澄清

用户说明：主要想不用原先的 VLM 模型而采用通用大模型，其他扩展没有细想，受到近期 OpenAI 和 Anthropic 模型在 RoboDojo 的表现启发。

助手承认此前把该偏好解读为扩展完整具身 Harness／操作任务，放大了用户意图。

## 概念与资料核对

- VLM 描述视觉与语言能力，不意味着机器人专用模型；具备图像输入的通用大模型可以同时看图、理解问题并调用动作工具。纯文本模型不能直接读取 RGB，若另加感知模块又会增加链路。
- 使用 OpenAI Docs 技能查阅 [图像输入](https://developers.openai.com/api/docs/guides/images-vision) 与 [工具调用](https://developers.openai.com/api/docs/guides/tools)。
- 核对 [Anthropic 2026-11-09 发布说明](https://www.anthropic.com/claude-fable-and-mythos-5-2)：其报告使用摄像头图像控制双臂仿真机器人，比较相同 harness 的通用模型；分数是其内部评测，不能和其他协议混比。
- 核对 [RoboDojo 中 GPT 模型的研究摘要](https://arxiv.org/abs/2609.24170)：研究无需任务专用微调的 LLM-as-policy；它是研究者评测 OpenAI 模型，不据此归因为 OpenAI 自己完成的机器人系统。
- 查阅范围为文档、发布说明、论文摘要与官方仓库，没有复现 RoboDojo、全文审计或实测 API。

## 项目更新

- 记录 D007，同步 README、PLAN v1.1、MEMORY、PROGRESS，保留历史讨论。
- 保留原 C6 任务、仿真器、数据与研究比较；模型方向改为优先通用多模态 API，具体 provider／型号待定。
- 不自动开展复杂恢复研究，不切换 RoboDojo，不部署或购买任何服务。
- 同一个通用模型接收问题和画面，输出动作；本地执行并回传画面／反馈，最终回答。无需单独的视觉模型服务。

## 后续工作

S01 仍是资源审计与最小接口；进一步优先确认可用模型 API、图片输入／工具调用及小样本成本。无新增消费授权，原预算仍为草案。

本轮仅改文档，提交前检查 diff／链接，提交后检查工作树。父提交：5511e9d。
