import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from pulse import Tail,Monitor
from progress import report,attach,validate
from panel import PanelModel,PanelPainter

A='00000000-0000-4000-8000-000000000911'
B='00000000-0000-4000-8000-000000000912'


class MilestoneReportsTests(unittest.TestCase):
    def test_real_report_transitions_refresh_an_open_panel_and_expire_next_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'sessions';source.mkdir();path=source/(A+'.jsonl')
            path.write_text(json.dumps(dict(type='event_msg',payload=dict(type='task_started',turn_id='turn-one')))+'\n')
            monitor=Monitor(source,A);model=PanelModel();painter=PanelPainter()
            steps=[dict(step='Diagnose',status='completed'),dict(step='Implement',status='in_progress'),dict(step='Validate',status='pending')]
            real_attach=attach
            with patch('progress.attach',side_effect=lambda state,ref:real_attach(state,ref,root)):
                report(dict(steps=steps),A,source,root)
                state,_,_=monitor.poll();model.update(state,A,[],'en');model.toggle(A)
                self.assertEqual(state.percent,33)
                self.assertEqual(state.current,'Implement')
                self.assertIn('Validate',state.next_step)
                text=' '.join(line[0] for line in painter.detail_lines(model.cards[0],'en'))
                self.assertIn('Progress · 33%',text)
                self.assertIn('1/3 steps · by plan',text)
                steps[1]['status']='completed';steps[2]['status']='in_progress'
                report(dict(steps=steps),A,source,root);monitor.last_poll=-10
                state,_,_=monitor.poll();model.update(state,A,[],'en',preserve_order=True)
                self.assertEqual(model.expanded,A)
                self.assertEqual(state.percent,67);self.assertEqual(state.current,'Validate')
                steps[2]['status']='completed';report(dict(steps=steps),A,source,root);monitor.last_poll=-10
                state,_,_=monitor.poll()
                self.assertEqual(state.percent,100);self.assertEqual(state.current,'Mərhələlər tamamlandı')
                with path.open('a') as stream:stream.write(json.dumps(dict(type='event_msg',payload=dict(type='agent_message',message='Now checking a different result')))+'\n')
                monitor.last_poll=-10;state,_,_=monitor.poll()
                self.assertEqual(state.current,'Now checking a different result')
                other=Tail(path).poll();other.turn_id='another-chat-turn';attach(other,B,root)
                self.assertIsNone(other.percent)
                with patch('progress.time.time',return_value=time.time()+130):
                    attach(state,A,root);self.assertIsNone(state.percent)
                with path.open('a') as stream:stream.write(json.dumps(dict(type='event_msg',payload=dict(type='task_started',turn_id='turn-two')))+'\n')
                monitor.last_poll=-10;state,_,_=monitor.poll()
                self.assertIsNone(state.percent);self.assertFalse(state.milestones)

    def test_rejects_invalid_or_inactive_reports_without_overwriting(self):
        for value in ({},{'steps':[]},{'steps':[{'step':'x','status':'fake'}]}, {'steps':[{'step':'a','status':'in_progress'},{'step':'b','status':'in_progress'}]}):
            with self.assertRaises(ValueError):validate(value)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/(A+'.jsonl');path.write_text('{}\n')
            with self.assertRaises(ValueError):report({'steps':[dict(step='A',status='completed')]},A,tmp,tmp)
            self.assertFalse((Path(tmp)/'progress').exists())


if __name__=='__main__':unittest.main()
