import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from jobs import qe_snapshot
from languages import DisplayState
from pulse import State


class LiveJobTests(unittest.TestCase):
    def write(self,root,name,value):
        (root/name).write_text(json.dumps(value),encoding='utf-8')

    def setup_job(self,root,status):
        self.write(root,'status.json',status)
        self.write(root,'plan.json',dict(stages=['strict_SCF_audit','I/O_validation','wave_cutoff'],wave_cutoff_limits_Ry=[90,100,110,120,130],SCF_Ry=1e-10))
        events=[dict(stage='wave_cutoff')]+[dict(stage='wave_cutoff_result',W=w,comparison=dict(passed=w==120)) for w in (90,100,110,120)]
        # A resumed controller may repeat results. Count each cutoff only once.
        (root/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events+events)+'\n')

    def test_memory_wait_is_not_active_computation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.setup_job(root,dict(status='waiting_memory',pending_case='old_w130_r560_k221',controller_pid=123,required_free_RAM_GB=8.82,available_RAM_GB=8.10))
            with patch('jobs.alive',return_value=True):s=qe_snapshot(root,'TlInS₂')
            self.assertFalse(s['active'])
            self.assertEqual(s['badge'],'WAIT')
            self.assertEqual(s['tone'],'amber')
            self.assertIn('8.10 / 8.82',s['metrics'])
            self.assertIn('130 Ry',s['current'])
            self.assertIn('old seed',s['title'])
            self.assertEqual(s['percent'],80)
            self.assertIn('4/5',s['scope'])
            state=DisplayState(State(background=s),'en')
            self.assertIn('Waiting for RAM',state.live_health)

    def test_current_iteration_and_last_residual_are_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.setup_job(root,dict(status='computing',case='old_w130_r560_k221',qe_pid=123))
            case=root/'old_w130_r560_k221';case.mkdir()
            (case/'scf.out').write_text('iteration # 1\nestimated scf accuracy < 1.4E-6 Ry\niteration # 2\n')
            with patch('jobs.alive',return_value=True),patch('jobs.process_metrics',return_value={'cpu_seconds':15}):s=qe_snapshot(root,'TlInS₂')
            self.assertTrue(s['active'])
            self.assertEqual(s['iteration'],2)
            self.assertEqual(s['accuracy_Ry'],1.4e-6)
            self.assertEqual(s['target_Ry'],1e-10)
            self.assertIn('1.40e-06',s['metrics'])
            self.assertIn('1e-10',s['metrics'])
            self.assertEqual(sum(step['status']=='completed' for step in s['steps']),4)
            self.assertEqual(s['steps'][-1]['status'],'in_progress')

    def test_finished_output_enters_audit_not_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.setup_job(root,dict(status='computing',case='old_w130_r560_k221',qe_pid=123))
            case=root/'old_w130_r560_k221';case.mkdir()
            (case/'scf.out').write_text('JOB DONE.\n')
            with patch('jobs.alive',return_value=True),patch('jobs.process_metrics',return_value={}):s=qe_snapshot(root)
            self.assertEqual(s['badge'],'CHECK')
            self.assertFalse(s['active'])
            self.assertNotEqual(s['percent'],100)


if __name__=='__main__':unittest.main()
