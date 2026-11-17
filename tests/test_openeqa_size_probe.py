"""冻结开发诊断的两个边界：只用匹配住宅的题，私有真值不进入推理。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import openeqa_size_probe as probe


class SizeProbeTest(unittest.TestCase):
    def test_pairs_share_questions_and_hide_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "views.json").write_text(json.dumps({"scene": probe.SCENE + ".basis.glb", "seed": 17}))
            rows = []
            for question_id, names in probe.CASES:
                rows.append(dict(question_id=question_id, question="Question " + question_id,
                                 episode_history="hm3d-v0/episode-" + probe.SCENE, answer="PRIVATE_GOLD"))
                for name in names + probe.DISTRACTORS:
                    (root / (name + ".png")).write_bytes(name.encode())
            questions = root / "bank.json"
            questions.write_text(json.dumps(rows))
            output = root / "result.json"
            argv = ["probe", "--backend", "mlx", "--size", "2", "--questions", str(questions),
                    "--views", str(root), "--output", str(output)]
            with patch.object(sys, "argv", argv), patch.object(probe, "mlx_engine") as factory:
                factory.return_value = (lambda text, images: (text, 1.0), {})
                probe.main()
                result = json.loads(output.read_text())["rows"]
                self.assertEqual(len(result), 6)
                for with_clues, closet in zip(result[::2], result[1::2]):
                    self.assertEqual(with_clues["raw"], closet["raw"])
                    self.assertNotIn("PRIVATE_GOLD", closet["raw"])
                    self.assertNotIn(probe.SCENE, closet["raw"])
                    self.assertEqual(closet["images"], probe.DISTRACTORS)
                    self.assertNotEqual(with_clues["images_sha256"], closet["images_sha256"])

            # 保留相同的问题 ID，但改为另一住宅，入口应在加载模型前退出。
            rows[0]["episode_history"] = "hm3d-v0/episode-other"
            questions.write_text(json.dumps(rows))
            argv[-1] = str(root / "wrong-scene.json")
            with patch.object(sys, "argv", argv), patch.object(probe, "mlx_engine") as engine:
                with self.assertRaises(SystemExit):
                    probe.main()
                engine.assert_not_called()
