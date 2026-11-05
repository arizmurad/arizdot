import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jobs import qe_snapshot, Jobs
from motion import Morph,Spring
from pulse import State


class MotionTests(unittest.TestCase):
    def test_spring_keeps_velocity_on_hover_reversal(self):
        m=Spring()
        m.aim(True,1)
        previous=m.value(1.07)
        velocity=m.velocity
        self.assertGreater(previous,0)
        self.assertEqual(m.aim(False,1.07,.23),previous)
        self.assertEqual(m.velocity,velocity)
        self.assertEqual(m.value(3),0)
        m.aim(True,3)
        self.assertEqual(m.value(5),1)

    def test_animation_endpoints_and_reversal(self):
        m=Morph(.28)
        self.assertEqual(m.aim(True,1),0)
        mid=m.value(1.14)
        self.assertAlmostEqual(mid,.5)
        self.assertEqual(m.aim(False,1.14),mid)
        self.assertAlmostEqual(m.value(1.42),0)
        m.aim(True,2)
        self.assertEqual(m.value(3),1)


class JobTests(unittest.TestCase):
    def fixture(self,root):
        def write(name,value):
            (root/name).write_text(json.dumps(value),encoding='utf-8')
        write('plan.json',dict(stages=['strict_SCF_audit','I/O_validation','wave_cutoff','density_cutoff']))
        write('status.json',dict(status='computing',case='old_w120_r560_k221_a1',qe_pid=123))
        (root/'events.jsonl').write_text(json.dumps(dict(stage='wave_cutoff'))+'\n')
        case=root/'old_w120_r560_k221_a1'
        case.mkdir()
        (case/'scf.out').write_text('iteration #  1\niteration #  2\n')

    def test_background_work_overrides_finished_reply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.fixture(root)
            with patch('jobs.alive',return_value=True):value=qe_snapshot(root)
            s=State(status='Tamamlandı',active=False,background=value)
            self.assertTrue(s.working)
            self.assertIsNone(s.percent)
            self.assertIn('120 Ry',s.current)
            self.assertIn('SCF 2',s.live_metrics)
            self.assertIn('auditi',s.next_step)

    def test_missing_worker_does_not_show_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.fixture(root)
            with patch('jobs.alive',return_value=False):value=qe_snapshot(root)
            self.assertFalse(value['active'])
            self.assertEqual(value['status'],'Proses tapılmadı')
            self.assertIsNone(value['percent'])

    def test_unreadable_bound_source_never_defaults_to_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bindings.json'
            p.write_text(json.dumps({'a':dict(adapter='qe',root=str(Path(tmp)/'missing'))}))
            value=Jobs(p).get('a')
            self.assertIsNone(value['percent'])
            self.assertFalse(value['active'])

    def test_reply_completion_without_plan_has_no_percentage(self):
        s=State()
        s.feed(dict(type='event_msg',payload=dict(type='task_complete')))
        self.assertIsNone(s.percent)


if __name__=='__main__':unittest.main()
