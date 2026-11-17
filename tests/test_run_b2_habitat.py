"""Check action parsing before model outputs can affect the simulator."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_b2_habitat import choose_action


class ActionParsingTest(unittest.TestCase):
    def test_fenced_action_is_executed(self):
        self.assertEqual(choose_action('```json\n{"action":"MoveAhead"}\n```', False),
                         ("MoveAhead", True))

    def test_prose_uses_recorded_fallback(self):
        self.assertEqual(choose_action("I cannot see the washing machine", False),
                         ("MoveAhead", False))
        self.assertEqual(choose_action("I cannot see the washing machine", True),
                         ("RotateRight", False))

    def test_unlisted_action_is_not_sent_to_simulator(self):
        self.assertEqual(choose_action('{"action":"Teleport"}', False),
                         ("MoveAhead", False))


if __name__ == "__main__":
    unittest.main()
