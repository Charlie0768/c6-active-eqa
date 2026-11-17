"""Check that a useful abstention survives a formatting failure."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from habitat_paired_pilot import normalize_prediction


class PredictionParsingTest(unittest.TestCase):
    def test_plain_unknown_keeps_semantic_answer_and_format_failure(self):
        self.assertEqual(normalize_prediction("unknown", 4), ("unknown", None, False))

    def test_json_answer_keeps_valid_citation(self):
        self.assertEqual(normalize_prediction('{"answer":"dryer","frame":2}', 4),
                         ("dryer", 2, True))

    def test_out_of_range_citation_is_rejected(self):
        self.assertEqual(normalize_prediction('{"answer":"dryer","frame":5}', 4),
                         (None, None, False))


if __name__ == "__main__":
    unittest.main()
