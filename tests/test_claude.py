import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from activation import caller_thread,session_ref,split_ref,valid_ref
from claude_support import record_hook,register,report_desktop,snapshot_state,session_path

A='00000000-0000-4000-8000-000000000001'
ROOT=Path(__file__).resolve().parents[1]


class ClaudeTests(unittest.TestCase):
    def event(self,tmp,kind,**fields):return record_hook(dict(session_id=A,hook_event_name=kind,**fields),root=tmp)

    def test_claude_ref_never_collides_with_codex(self):
        self.assertNotEqual(session_ref(A,'claude'),session_ref(A))
        self.assertEqual(split_ref('claude:'+A),('claude',A))
        self.assertFalse(valid_ref('claude:../../private'))
        with patch.dict(os.environ,{'CODEX_THREAD_ID':A,'CLAUDE_SESSION_ID':A}):
            self.assertEqual(caller_thread(provider='claude'),'claude:'+A)
        with self.assertRaises(ValueError):caller_thread('not-a-session','claude')

    def test_stop_keeps_real_plan_fraction_not_100(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.event(tmp,'UserPromptSubmit',prompt_id='turn-one')
            self.event(tmp,'PostToolUse',tool_name='TodoWrite',tool_input=dict(todos=[dict(content='Read inputs',status='completed'),dict(content='Check result',status='in_progress')]))
            self.event(tmp,'Stop',last_assistant_message='Partial result')
            state=snapshot_state(A,'claude',tmp)
            self.assertEqual(state.percent,50)
            self.assertEqual(state.background['phase'],'completed')
            self.assertFalse(state.working)

    def test_background_task_after_stop_is_not_completed_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.event(tmp,'Stop',background_tasks=[dict(id='worker-1')])
            state=snapshot_state(A,'claude',tmp)
            self.assertTrue(state.working)
            self.assertEqual(state.background['phase'],'background')
            self.assertIsNone(state.percent)

    def test_permissions_and_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.event(tmp,'PermissionRequest')
            self.assertFalse(snapshot_state(A,'claude',tmp).working)
            self.assertEqual(snapshot_state(A,'claude',tmp).live_badge,'WAIT')
            self.event(tmp,'StopFailure')
            self.assertEqual(snapshot_state(A,'claude',tmp).background['phase'],'needs_review')

    def test_no_raw_shell_arguments_or_user_prompt_are_copied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.event(tmp,'UserPromptSubmit',prompt='secret-user-prompt')
            self.event(tmp,'PreToolUse',tool_name='Bash',tool_input={'command':'token=secret-value'})
            value=session_path(A,root=tmp).read_text(encoding='utf-8')
            self.assertNotIn('secret',value)
            self.assertIn('Bash',value)

    def test_tasks_are_updated_after_success_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.event(tmp,'PreToolUse',tool_name='TaskCreate',tool_input=dict(subject='Not yet created'))
            self.assertIsNone(snapshot_state(A,'claude',tmp).percent)
            self.event(tmp,'PostToolUse',tool_name='TaskCreate',tool_input=dict(subject='Task A'),tool_response={'task':{'id':'7'}})
            self.event(tmp,'PostToolUse',tool_name='TaskUpdate',tool_input=dict(taskId='7',status='completed'))
            self.assertEqual(snapshot_state(A,'claude',tmp).percent,100)

    def test_missing_and_stale_sources_are_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(snapshot_state(A,'claude',tmp).freshness,'offline')
            self.event(tmp,'PreToolUse',tool_name='Read')
            with patch('claude_support.time.time',return_value=10**12):self.assertEqual(snapshot_state(A,'claude',tmp).freshness,'stale')

    def test_reported_desktop_values_are_not_observed_telemetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_desktop(A,'Report','Writing section',2,5,root=tmp)
            state=snapshot_state(A,'claude-desktop',tmp)
            self.assertEqual(state.percent,40)
            self.assertEqual(state.freshness,'recorded')
            self.assertFalse(state.working)
            self.assertTrue(state.background['reported'])
            with self.assertRaises(ValueError):report_desktop(A,'Report','Invalid',8,5,root=tmp)
            self.assertEqual(snapshot_state(A,'claude-desktop',tmp).percent,40)

    def test_named_milestones_and_counts_must_agree_without_mutating_last_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            steps=[dict(step='Read inputs',status='completed'),dict(step='Review',status='in_progress')]
            report_desktop(A,'Report','Reviewing',steps=steps,root=tmp)
            self.assertEqual(snapshot_state(A,'claude-desktop',tmp).percent,50)
            report_desktop(A,'Report','Still reviewing',root=tmp)
            self.assertFalse(snapshot_state(A,'claude-desktop',tmp).plan)
            for bad in ([dict(step='Incorrect',status='unknown')],[dict(step=' ',status='completed')]):
                with self.assertRaises(ValueError):report_desktop(A,'Report','Invalid',steps=bad,root=tmp)
            for done,total in ((2,2),(True,2),(None,2)):
                with self.assertRaises(ValueError):report_desktop(A,'Report','Invalid',done,total,steps=steps,root=tmp)
            self.assertEqual(snapshot_state(A,'claude-desktop',tmp).current,'Still reviewing')
            self.assertIsNone(snapshot_state(A,'claude-desktop',tmp).percent)

    def test_hook_failure_does_not_block_claude_or_pollute_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            env=os.environ.copy();env['ARIZDOT_DATA_DIR']=tmp
            result=subprocess.run([sys.executable,str(ROOT/'claude_hook.py')],input=b'not-json',capture_output=True,env=env)
            self.assertEqual(result.returncode,0)
            self.assertEqual(result.stdout,b'')
            self.assertNotIn(b'not-json',result.stderr)

    def test_provider_aware_return_links(self):
        import navigation
        with patch('navigation.os.startfile',create=True) as launch,patch('claude_support.read_snapshot',return_value={'conversation_id':A}):
            self.assertTrue(navigation.open_thread('claude-desktop:'+A)['exact'])
            launch.assert_called_once_with('claude://claude.ai/chat/'+A)
        with patch('navigation.os.startfile',create=True) as launch,patch('shutil.which',return_value=None):
            self.assertFalse(navigation.open_thread('claude:'+A)['exact'])
            launch.assert_called_once_with('claude://claude.ai/chat/')


if __name__=='__main__':unittest.main()
