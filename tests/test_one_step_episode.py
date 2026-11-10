"""Boundary checks for the one-action episode without starting Unity or MLX."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from one_step_episode import action_success, consume_action, make_observation, make_prompt


class OneStepBoundaryTests(unittest.TestCase):
    def test_attempt_counts_before_success_is_known(self):
        used = consume_action("RotateRight", used=0, budget=1)
        self.assertEqual(used, 1)
        with self.assertRaisesRegex(RuntimeError, "budget exhausted"):
            consume_action("RotateRight", used=used, budget=1)
        with self.assertRaisesRegex(ValueError, "not allowed"):
            consume_action("Teleport", used=0, budget=1)

    def test_hidden_metadata_cannot_enter_model_input(self):
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
