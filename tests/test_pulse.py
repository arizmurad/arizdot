import json
import tempfile
import unittest
from pathlib import Path
from pulse import State, Tail, Monitor


def event(kind, **kwargs):
    return dict(type="event_msg", payload=dict(type=kind, **kwargs))


class PulseTests(unittest.TestCase):
    def test_concrete_activity_from_commentary(self):
        s = State()
        s.feed(event("task_started"))
        s.feed(event("item_completed", item=dict(type="AgentMessage", phase="commentary", content=[dict(type="Text", text="Sənəddəki cədvəlləri yoxlayıram.")])))
        s.feed(event("item_completed", item=dict(type="CommandExecution")))
        self.assertEqual(s.current, "Sənəddəki cədvəlləri yoxlayıram.")
        s.feed(event("task_started"))
        self.assertEqual(s.detail, "")

    def test_plan_takes_precedence_over_commentary(self):
        s = State(detail="Hazırlayıram")
        s.set_plan([dict(step="Cədvəllərin yoxlanması",status="in_progress")])
        self.assertEqual(s.current,"Cədvəllərin yoxlanması")

    def test_lifecycle_resets_plan(self):
        s = State()
        s.feed(event("task_started"))
        self.assertTrue(s.active)
        self.assertIsNone(s.percent)
        s.set_plan([dict(step="A", status="completed"), dict(step="B", status="in_progress")])
        self.assertEqual(s.percent, 50)
        s.feed(event("task_complete"))
        self.assertEqual(s.percent, 50)
        s.feed(event("task_started"))
        self.assertIsNone(s.percent)

    def test_current_desktop_items(self):
        s = State()
        s.feed(event("task_started"))
        s.feed(event("item_completed", item=dict(type="Extension", kind="web.search")))
        self.assertEqual(s.stage, "Məlumat axtarır")
        s.feed(event("item_completed", item=dict(type="AgentMessage", phase="final")))
        self.assertFalse(s.active)

    def test_plan_tool(self):
        s = State()
        s.tool("functions.update_plan", json.dumps(dict(plan=[dict(step="Test", status="in_progress")])))
        self.assertEqual(s.percent, 0)
        self.assertEqual(s.stage, "Test")

    def test_partial_line_and_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.jsonl"
            data = json.dumps(event("task_started")).encode()
            p.write_bytes(b"invalid\n" + data[:10])
            tail = Tail(p)
            self.assertFalse(tail.poll().active)
            with p.open("ab") as f:
                f.write(data[10:] + b"\n")
            self.assertTrue(tail.poll().active)
            p.write_bytes(b"{}\n")
            self.assertFalse(tail.poll().active)

    def test_session_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("a", "b"):
                (Path(tmp) / (name + ".jsonl")).write_text(json.dumps(event("task_started")) + "\n")
            s, count, sid = Monitor(tmp, "a").poll()
            self.assertEqual(count, 1)
            self.assertTrue(s.active)

    def test_abort_is_not_completion(self):
        s = State()
        s.feed(event("task_started"))
        s.feed(event("turn_aborted"))
        self.assertFalse(s.active)
        self.assertIsNone(s.percent)


if __name__ == "__main__":
    unittest.main()
