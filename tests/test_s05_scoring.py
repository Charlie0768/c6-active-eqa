"""S05 评分与输入隔离测试，不需要启动 Unity 或加载模型。"""

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_b0 import make_prompt, pose_matches
from score_answers import normalize_answer, score_rows


class S05ScoringTests(unittest.TestCase):
    def setUp(self):
        self.questions = [
            {"id": "q1", "question_type": "yes_no_presence"},
            {"id": "q2", "question_type": "yes_no_attribute"},
        ]
        self.labels = [{"id": "q1", "answer": "是"}, {"id": "q2", "answer": "否"}]

    def test_hand_calculated_accuracy_and_efficiency(self):
        predictions = [
            {"id": "q1", "answer": "yes", "valid_answer_json": True, "actions_used": 10},
            {"id": "q2", "answer": "不确定", "valid_answer_json": True, "actions_used": 0},
        ]
        # q1 正确，效率 1-10/(2*20)=0.75；q2 错误，效率 0；均值 0.375。
        result = score_rows(self.questions, self.labels, predictions)
        self.assertEqual(result["accuracy"], 0.5)
        self.assertEqual(result["mean_actions"], 5)
        self.assertEqual(result["mean_actions_when_correct"], 10)
        self.assertEqual(result["mean_correct_action_efficiency"], 0.375)

    def test_invalid_or_missing_output_stays_in_denominator(self):
        predictions = [
            {"id": "q1", "answer": "是", "valid_answer_json": False, "actions_used": 0},
            {"id": "q2", "answer": None, "valid_answer_json": False, "actions_used": 0},
        ]
        result = score_rows(self.questions, self.labels, predictions)
        self.assertEqual(result["question_count"], 2)
        self.assertEqual(result["correct_count"], 0)
        self.assertIsNone(result["mean_actions_when_correct"])
        self.assertIsNone(normalize_answer("不是"))

    def test_duplicate_missing_and_over_budget_are_rejected(self):
        predictions = [
            {"id": "q1", "answer": "是", "valid_answer_json": True, "actions_used": 0},
            {"id": "q1", "answer": "否", "valid_answer_json": True, "actions_used": 0},
        ]
        with self.assertRaisesRegex(ValueError, "duplicate prediction"):
            score_rows(self.questions, self.labels, predictions)
        with self.assertRaisesRegex(ValueError, "IDs must match"):
            score_rows(self.questions, self.labels, predictions[:1])
        predictions[1]["id"] = "q2"
        predictions[1]["actions_used"] = 21
        with self.assertRaisesRegex(ValueError, "invalid actions_used"):
            score_rows(self.questions, self.labels, predictions)

    def test_public_dataset_and_prompt_exclude_private_labels(self):
        public = json.loads((ROOT / "data/dev_questions.json").read_text(encoding="utf-8"))
        private = json.loads((ROOT / "data/dev_labels.json").read_text(encoding="utf-8"))
        self.assertEqual(set(row["id"] for row in public["questions"]),
                         set(row["id"] for row in private["labels"]))
        for row in public["questions"]:
            self.assertNotIn("answer", row)
            self.assertNotIn("evidence", row)
            self.assertNotIn("reference_actions", row)
            prompt = make_prompt(row["question"])
            self.assertIn(row["question"], prompt)
            self.assertNotIn("reference_actions", prompt)
        self.assertNotIn("dev_labels", Path(ROOT / "scripts/run_b0.py").read_text(encoding="utf-8").split('import argparse', 1)[1])

    def test_pose_check_wraps_yaw_and_rejects_wrong_start(self):
        expected = {"position": {"x": -1.0, "y": 0.9, "z": 1.0},
                    "yaw_degrees": 270.0, "camera_horizon_degrees": 0.0}
        metadata = {"agent": {"position": {"x": -1.0, "y": 0.9, "z": 1.0},
                              "rotation": {"y": -90.0}, "cameraHorizon": 0.0}}
        self.assertTrue(pose_matches(metadata, expected))
        metadata["agent"]["position"]["z"] = 1.25
        self.assertFalse(pose_matches(metadata, expected))


if __name__ == "__main__":
    unittest.main()
