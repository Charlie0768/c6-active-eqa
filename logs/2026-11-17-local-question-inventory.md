# 本地 OpenEQA 题目盘点与第二道开发题

用户问下一步。本轮先检查本地场景、导航网格、题目 ID 和起点来源，再在同一住宅试第二道题。生成器 `scripts/inventory_local_hm3d.py` 从官方 JSON 中只投影问题、ID、类别和 episode_history，输出 `data/local_hm3d_dev_inventory.json`。11 道题全部属于 GLAQ4DNUx5U。已有三个样例场景及配套 navmesh，另外两个与此题库中的 HM3D 问题没有交集。清单标记为开发候选，尚未做题目可达性审核或正式切分。

当前起点来自 Habitat 以 seed 17 采样的可行走点，已登记位置、朝向和起始 RGB 哈希。它不是 OpenEQA 官方 episode 历史位姿。本地 `data/raw/route-a/states.tgz` 是 HTML，不能当压缩包使用。官方 [OpenEQA 数据说明](https://github.com/facebookresearch/open-eqa/blob/main/data/README.md)要求完整 HM3D 验证集及 agent state 文件才能提取原始 episode 历史；当前路径不具备这些数据。项目测试题应留到更多住宅取得后再按住宅隔离。

选择官方问题 `91a12c51-1ca0-4651-902a-c5aaeb62534f`，题干为“客厅沙发是什么形状”，参考答案 C 形。用当前 B2、相同 seed 17 起点、本地 2B 4-bit、960×540 走满 20 步，结果位于 `runs/habitat-couch-b2-strategy-v2-20/`。记录 21 张画面和 20 条决策，13 次前进、7 次转向、5 次碰撞，离起点最远 1.319 米。答案为 `rectangular`，JSON 格式有效，引用第 13 帧。人工查看第 7、13、20 帧，第 13 帧只能看到沙发局部，不能据此确认整体为矩形或 C 形。故本次答案与参考不符，引用帧证据不足；轨迹是否在别的帧拍到完整轮廓还需逐帧标注。

21 张 RGB 哈希、步号、动作数和与洗衣机 B2 相同起始帧均已核对。该题与此前洗衣机题都属于开发诊断，不计入正式测试。下一工作单应在开发题上标注轨迹有无充分证据，并核查四图是否保留，再调整选帧和停止规则。
