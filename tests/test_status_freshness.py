import tempfile
import time
import unittest
from unittest.mock import patch
from claude_support import record_hook,report_desktop,snapshot_state,report_code
from panel import PanelModel,PanelPainter
from pulse import State

A='00000000-0000-4000-8000-000000000921'


class StatusFreshnessTests(unittest.TestCase):
    def test_newer_concurrent_payload_is_not_overwritten_by_cached_selected_row(self):
        from pathlib import Path
        for ref in (A,'claude:'+A,'claude-desktop:'+A):
            old=State(active=True,detail='Old operation',session_ref=ref,source_modified=time.time()-1)
            new=State(active=True,detail='New operation',session_ref=ref,source_modified=time.time())
            model=PanelModel();model.update(old,ref,[],'en');model.toggle(ref)
            model.update(old,ref,[(new,Path(A))],'en',preserve_order=True)
            self.assertEqual(model.cards[0].current,'New operation');self.assertEqual(model.expanded,ref)

    def test_claude_code_live_operation_supersedes_old_task_and_plan_has_own_expiry(self):
        with tempfile.TemporaryDirectory() as tmp:
            def event(kind,**kw):return record_hook(dict(session_id=A,hook_event_name=kind,**kw),tmp)
            event('UserPromptSubmit')
            report_code(A,[dict(step='Old task label',status='in_progress'),dict(step='Review',status='pending')],tmp)
            event('PreToolUse',tool_use_id='r',tool_name='Read',tool_input={'file_path':'C:/new-result.txt'})
            self.assertIn('new-result.txt',snapshot_state(A,'claude',tmp).current)
            event('PostToolUse',tool_use_id='r',tool_name='Read',tool_input={'file_path':'C:/new-result.txt'})
            self.assertNotIn('Old task label',snapshot_state(A,'claude',tmp).current)
            future=time.time()+125
            with patch('claude_support.time.time',return_value=future):
                event('PreToolUse',tool_use_id='e',tool_name='Edit')
                state=snapshot_state(A,'claude',tmp)
                self.assertEqual(state.freshness,'live');self.assertIsNone(state.percent);self.assertFalse(state.next_step)
            event('UserPromptSubmit');self.assertFalse(snapshot_state(A,'claude',tmp).plan)

    def test_desktop_omitted_plan_clears_old_counts_and_new_turn_updates_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            first=report_desktop(A,'Old title','Old work',steps=[dict(step='Old',status='in_progress')],root=tmp)
            report_desktop(A,'New title','New work',new_turn=True,root=tmp)
            state=snapshot_state(A,'claude-desktop',tmp)
            self.assertNotEqual(first['turn_id'],state.turn_id)
            self.assertEqual(state.live_title,'New title');self.assertEqual(state.current,'New work')
            self.assertIsNone(state.percent);self.assertFalse(state.plan);self.assertFalse(state.next_step)

    def test_stale_provider_rows_do_not_present_old_work_or_percentage_as_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_desktop(A,'Task','Old work',1,2,next_step='Old target',root=tmp)
            with patch('claude_support.time.time',return_value=time.time()+150):state=snapshot_state(A,'claude-desktop',tmp)
            self.assertEqual(state.current,'Yeni status məlumatı gözlənilir');self.assertIsNone(state.percent)
            model=PanelModel();model.update(state,'claude-desktop:'+A,[],'en')
            text=' '.join(v[0] for v in PanelPainter().detail_lines(model.cards[0],'en'))
            self.assertIn('Waiting for a new status update',text)
            self.assertNotIn('Old work',text);self.assertNotIn('Old target',text)
            codex=State(active=True,detail='Old Codex work',source_modified=time.time()-200,plan=[dict(step='Old',status='in_progress')])
            self.assertEqual(codex.current,'Yeni status məlumatı gözlənilir');self.assertIsNone(codex.percent)


if __name__=='__main__':unittest.main()
