"""B1 纯逻辑测试：固定随机序列、帧选择和模型输入边界。"""

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_b1_random import RANDOM_ACTIONS, make_prompt, sample_actions, select_frame_steps


class B1RandomTests(unittest.TestCase):
    def test_same_seed_replays_same_actions_within_budget(self):
        first = sample_actions(seed=17, budget=20)
        self.assertEqual(first, sample_actions(seed=17, budget=20))
        self.assertEqual(len(first), 20)
        self.assertTrue(all(action in RANDOM_ACTIONS for action in first))
        with self.assertRaisesRegex(ValueError, "budget"):
            sample_actions(seed=17, budget=21)

    def test_frame_selection_includes_start_and_end_without_peeking(self):
        self.assertEqual(select_frame_steps(20), [0, 7, 13, 20])
        self.assertEqual(select_frame_steps(1), [0, 1])
        self.assertEqual(select_frame_steps(0), [0])
        with self.assertRaisesRegex(ValueError, "frame selection"):
            select_frame_steps(20, max_images=1)

    def test_prompt_contains_only_question_and_frame_count(self):
        prompt = make_prompt("房门是白色的吗？", 4)
        self.assertIn("房门是白色的吗？", prompt)
        self.assertIn("4 张", prompt)
        self.assertNotIn("RotateRight", prompt)
        self.assertNotIn("gold_answer", prompt)


if __name__ == "__main__":
    unittest.main()
