import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from pulse import State,Tail
from panel import PanelModel,PanelPainter
from claude_support import record_hook,report_desktop,snapshot_state

A='00000000-0000-4000-8000-000000000901'


class LiveProgressTests(unittest.TestCase):
    def test_new_commentary_is_not_hidden_by_an_old_in_progress_plan(self):
        state=State(active=True)
        state.set_plan([dict(step='Earlier work',status='in_progress'),dict(step='Review',status='pending')])
        state.message('Now validating the new result')
        self.assertEqual(state.current,'Now validating the new result')
        state.set_plan([dict(step='Earlier work',status='completed'),dict(step='Review',status='in_progress')])
        self.assertEqual(state.current,'Review')
        self.assertEqual(state.percent,50)

    def test_completed_commands_flow_from_appended_source_to_open_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/(A+'.jsonl');path.touch();tail=Tail(path);model=PanelModel();painter=PanelPainter()
            def feed(row):
                with path.open('a',encoding='utf-8') as stream:stream.write(json.dumps(row)+'\n')
                state=tail.poll();state.session_ref=A
                model.update(state,A,[(state,path)],'en',preserve_order=True)
                return state
            feed(dict(type='event_msg',payload=dict(type='task_started')))
            model.expanded=A
            feed(dict(type='response_item',payload=dict(type='function_call',name='exec_command',call_id='c1',arguments='{}')))
            self.assertTrue(tail.state.current_action)
            for index in range(1,11):
                state=feed(dict(type='event_msg',payload=dict(type='item_completed',item=dict(type='CommandExecution',id='cmd'+str(index),status='completed',exit_code=0))))
                self.assertEqual(model.expanded,A)
                self.assertEqual(state.completed_actions[-1]['sequence'],index)
                self.assertEqual(model.cards[0].completed,())
            feed(dict(type='response_item',payload=dict(type='function_call_output',call_id='c1',output='done')))
            self.assertFalse(state.current_action)
            self.assertIsNone(state.percent)
            text=' '.join(line[0] for line in painter.detail_lines(model.cards[0],'en'))
            self.assertIn('Progress · milestone plan not reported',text)
            self.assertNotIn('Tool action',text)
            self.assertNotIn('Command action',text)
            self.assertEqual(len(state.completed_actions),8)

    def test_new_claude_report_current_is_visible_without_resending_old_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            steps=[dict(step='Read',status='completed'),dict(step='Draft',status='in_progress'),dict(step='Review',status='pending')]
            report_desktop(A,'Task','Draft',steps=steps,root=tmp)
            report_desktop(A,'Task','Run final validation',next_step='Deliver result',root=tmp)
            state=snapshot_state(A,'claude-desktop',tmp)
            self.assertEqual(state.current,'Run final validation')
            self.assertEqual(state.next_step,'Deliver result')
            self.assertIsNone(state.percent)
            self.assertFalse(state.plan)
            report_desktop(A,'Task','Review',steps=[dict(step='Read',status='completed'),dict(step='Draft',status='completed'),dict(step='Review',status='in_progress')],root=tmp)
            self.assertEqual(snapshot_state(A,'claude-desktop',tmp).percent,67)

    def test_claude_hooks_record_real_action_transitions_without_raw_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            def event(kind,**fields):return record_hook(dict(session_id=A,hook_event_name=kind,**fields),root=tmp)
            event('UserPromptSubmit')
            event('PreToolUse',tool_name='Read',tool_use_id='r1',tool_input={'file_path':'C:/private/input.txt'})
            self.assertIn('input.txt',snapshot_state(A,'claude',tmp).current)
            event('PostToolUse',tool_name='Read',tool_use_id='r1',tool_input={'file_path':'C:/private/input.txt'})
            event('PreToolUse',tool_name='Edit',tool_use_id='e1',tool_input={'file_path':'C:/private/result.txt','new_string':'secret'})
            state=snapshot_state(A,'claude',tmp)
            self.assertIn('result.txt',state.current)
            self.assertEqual(len(state.completed_actions),1)
            self.assertNotIn('secret',json.dumps(state.completed_actions))

    def test_stale_desktop_report_is_not_presented_as_current_live_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_desktop(A,'Task','Old work',next_step='Old target',root=tmp)
            with patch('claude_support.time.time',return_value=time.time()+300):state=snapshot_state(A,'claude-desktop',tmp)
            model=PanelModel();model.update(state,'claude-desktop:'+A,[],'en')
            text=' '.join(line[0] for line in PanelPainter().detail_lines(model.cards[0],'en'))
            self.assertIn('Last recorded work',text)
            self.assertNotIn('Working now',text)


if __name__=='__main__':unittest.main()
