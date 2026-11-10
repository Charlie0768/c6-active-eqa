"""S04 边界测试：不启动 Unity/MLX，只检查预算与信息隔离规则。"""

import json
import sys
import unittest
from pathlib import Path

# 使测试能直接导入 scripts 下的纯函数，不依赖安装项目包。
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from one_step_episode import action_success, consume_action, make_observation, make_prompt


class OneStepBoundaryTests(unittest.TestCase):
    def test_attempt_counts_before_success_is_known(self):
        """一次尝试立即占满预算，且未列入白名单的动作被拒绝。"""
        used = consume_action("RotateRight", used=0, budget=1)
        self.assertEqual(used, 1)
        with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
            consume_action("RotateRight", used=used, budget=1)
        with self.assertRaisesRegex(ValueError, "not allowed"):
            consume_action("Teleport", used=0, budget=1)

    def test_hidden_metadata_cannot_enter_model_input(self):
        """伪造隐藏答案，确保清单和提示词都没有泄漏它。"""
        # 即使仿真 metadata 含对象列表/答案，模型接口也只取动作成功布尔值。
        metadata = {"lastActionSuccess": False, "objects": [{"secret": "HIDDEN_ANSWER"}],
                    "answer": "HIDDEN_ANSWER"}
        success = action_success(metadata)
        observation = make_observation(
            "是否看到冰箱？",
            [{"frame_number": 1, "file": "frame1.png", "sha256": "a"},
             {"frame_number": 2, "file": "frame2.png", "sha256": "b"}],
            "RotateRight", success, used=1, budget=1,
        )
        self.assertEqual(set(observation),
                         {"question", "frames", "previous_action", "actions_used", "action_budget"})
        self.assertNotIn("HIDDEN_ANSWER", json.dumps(observation) + make_prompt(observation))
        self.assertFalse(observation["previous_action"]["success"])


if __name__ == "__main__":
    unittest.main()
