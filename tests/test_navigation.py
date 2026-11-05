import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from navigation import Navigation, thread_url, open_thread,bind_thread,claude_chat_url

A = "00000000-0000-4000-8000-000000000101"
B = "00000000-0000-4000-8000-000000000102"


def route(stamp, thread):
    return f"{stamp} info IAB_LIFECYCLE received browser sidebar owner sync ownerRoutePath=/local/{thread} windowId=1\n"


class NavigationTests(unittest.TestCase):
    def test_original_claude_chat_binding_preserves_progress_and_reports(self):
        from claude_support import report_desktop,read_snapshot,session_path
        with tempfile.TemporaryDirectory() as tmp:
            report_desktop(A,'Task','Check result',1,3,root=tmp)
            ref='claude-desktop:'+A
            self.assertEqual(bind_thread(ref,'https://claude.ai/chat/'+B,root=tmp),'claude://claude.ai/chat/'+B)
            value=read_snapshot(session_path(A,'claude-desktop',tmp))
            self.assertEqual(value['completed'],1)
            self.assertEqual(value['conversation_id'],B)
            report_desktop(A,'Task','Write report',2,3,root=tmp)
            self.assertEqual(read_snapshot(session_path(A,'claude-desktop',tmp))['conversation_id'],B)
            with self.assertRaises(ValueError):bind_thread(ref,'https://claude.ai/share/'+A,root=tmp)
            self.assertEqual(read_snapshot(session_path(A,'claude-desktop',tmp))['conversation_id'],B)

    def test_unbound_desktop_task_requests_its_link_without_opening_another_chat(self):
        with patch('claude_support.read_snapshot',return_value={}),patch('navigation.os.startfile',create=True) as launch:
            result=open_thread('claude-desktop:'+A)
            self.assertTrue(result['needs_link']);self.assertFalse(result['exact'])
            launch.assert_not_called()
        for url in ('https://evil.example/chat/'+B,'https://claude.ai.evil.example/chat/'+B,'javascript:alert(1)'):
            with self.assertRaises(ValueError):claude_chat_url(url)

    def test_open_chat_changes_without_new_task_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"desktop.log"
            p.write_text(route("2026-11-02T07:40:00.000Z", A))
            n = Navigation([Path(tmp)])
            self.assertEqual(n.poll(),A)
            with p.open("a") as f:
                f.write(route("2026-11-02T07:41:00.000Z",B))
                f.write(f"2026-11-02T07:42:00.000Z response_routed conversationId={A}\n")
            self.assertEqual(n.poll(),B)

    def test_out_of_order_files_and_partial_line(self):
        n = Navigation([])
        n.consume(route("2026-11-02T07:41:00.000Z",B))
        n.consume(route("2026-11-02T07:40:00.000Z",A))
        self.assertEqual(n.thread,B)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"desktop.log"
            data = route("2026-11-02T07:42:00.000Z",A)
            p.write_text(data[:-1])
            n = Navigation([Path(tmp)])
            self.assertIsNone(n.poll())
            with p.open("a") as f:f.write("\n")
            self.assertEqual(n.poll(),A)

    def test_double_click_target_is_exact_thread_url(self):
        with patch("navigation.os.startfile",create=True) as launch:
            open_thread(B)
            launch.assert_called_once_with("codex://threads/"+B)
        with self.assertRaises(ValueError):
            thread_url("../../settings")

    def test_route_with_host_query(self):
        n=Navigation([])
        n.consume(route("2026-11-02T07:41:00.000Z",B+"?hostId=local"))
        self.assertEqual(n.thread,B)


if __name__ == "__main__":
    unittest.main()
