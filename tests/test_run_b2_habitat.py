"""Check action parsing before model outputs can affect the simulator."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_b2_habitat import choose_action, parse_action


class ActionParsingTest(unittest.TestCase):
    def test_fenced_action_is_executed(self):
        self.assertEqual(parse_action('```json\n{"action":"MoveAhead"}\n```'),
                         ("MoveAhead", "json"))
        self.assertEqual(parse_action('The next action is\n{"action":"RotateRight"}'),
                         ("RotateRight", "embedded_json"))
        self.assertEqual(parse_action('Action: Rotate Left'), ("RotateLeft", "action_text"))
        self.assertEqual(parse_action('"MoveAhead"'), ("MoveAhead", "json_string"))

    def test_prose_uses_recorded_fallback(self):
        proposed, _ = parse_action("I cannot see the washing machine")
        self.assertEqual(choose_action(proposed, False, 0),
                         ("MoveAhead", "missing_action_fallback"))
        self.assertEqual(choose_action(proposed, True, 0),
                         ("RotateRight", "collision_recovery"))

    def test_unlisted_action_is_not_sent_to_simulator(self):
        self.assertEqual(parse_action('{"action":"Teleport"}'), (None, "json"))
        self.assertEqual(parse_action('{"action":"MoveAhead"} {"action":"RotateLeft"}'),
                         (None, "ambiguous"))
        self.assertEqual(choose_action(None, False, 2), ("MoveAhead", "turn_limit"))
        self.assertEqual(choose_action("MoveAhead", True, 0),
                         ("RotateRight", "collision_recovery"))


if __name__ == "__main__":
    unittest.main()
