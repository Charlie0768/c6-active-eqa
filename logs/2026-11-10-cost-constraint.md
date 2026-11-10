# 2026-11-10 · 通用模型成本约束

用户补充：GPT 和 Claude 太贵。记录为选择低成本 API 的偏好，而非要求取消视觉输入或购买任何替代服务。

## 当日官方资料

- [Qwen3.8-Flash 能力](https://help.aliyun.com/en/model-studio/qwen3-8-flash)：图像／文本／视频输入、Function Calling 和结构化输出。
- [百炼价格](https://help.aliyun.com/zh/model-studio/model-pricing)：华北2北京，qwen3.8-flash，0 < 单请求输入 token <= 1M，标准输入 ¥0.8／百万 token，输出（含思考）¥2.7／百万 token。其他地域、优惠及免费额度条件可能不同。
- [GLM-4.6V-Flash](https://docs.bigmodel.cn/cn/guide/models/free/glm-4.6v-flash)：官方标注免费，支持图像输入和 Function Calling。尚未核对个人账户并发／限流，也未实测任务质量。
- [旧 qwen-flash](https://help.aliyun.com/en/model-studio/qwen-flash) 是纯文本输入，不能因为价格低就把它与 qwen3.8-flash 的视觉能力混为一谈。

## 示例估算，非实测

假设每次调用总输入为 8,000 token（包括图像、问题和历史），总计费输出为 500 token（包括思考等计费内容），1000 次调用：8 百万输入 × ¥0.8 + 0.5 百万输出 × ¥2.7 = ¥7.75。
这是条件化算例，不是整个项目报价；不含仿真服务器、额外评审、重试等。实际输入累积和思考输出可能显著改变费用，需 pilot 测量。

## 建议与工作记录

- Qwen3.8-Flash 作为低成本通用多模态候选；GLM-4.6V-Flash 作为免费开发原型候选。最终型号未确定，不保证具身能力等同 GPT／Claude。
- 免费原型模型若不作为正式模型，切换后需使用同一正式模型重跑所有主比较，不能混合计分。
- 同步 README、PLAN v1.2、MEMORY、PROGRESS、DECISIONS；只更新文档，无安装／API／充值。
- 下一步仍是 S01，包含核对机器环境与候选 API 可用性。用户尚未授权具体付费调用。
- 父提交 f72769c；提交前检查文档链接及 diff，提交后检查工作树。
