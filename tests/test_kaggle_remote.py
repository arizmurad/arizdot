from datetime import datetime,timezone
import json
import time
import unittest
from unittest.mock import patch
from kaggle_remote import MarkerReader,snapshot,Reader


class RemoteEvidenceTests(unittest.TestCase):
    def test_oauth_callback_codes_are_redacted_from_helper_console(self):
        from connect_kaggle import redact_callback
        self.assertNotIn('private-code',redact_callback('GET /?code=private-code&state=abc HTTP/1.1'))
    def test_chunked_real_remote_markers_preserve_identity_and_never_copy_pid_or_secrets(self):
        binding=dict(kernel='example/private-job',marker='EXAMPLE_STATUS',expected_cases=['case-a'])
        parser=MarkerReader(binding)
        value=dict(status='computing',updated_UTC=datetime.now(timezone.utc).isoformat(),case='case-a',iteration=8,qe_process_alive=True,qe_pid=999,error='secret')
        line='EXAMPLE_STATUS '+json.dumps(value)+'\n'
        self.assertFalse(parser.feed(line[:30]));rows=parser.feed(line[30:])
        self.assertEqual(rows[0]['iteration'],8)
        self.assertNotIn('qe_pid',rows[0]);self.assertNotIn('secret',json.dumps(rows))
        value['case']='different-run';self.assertFalse(parser.feed('EXAMPLE_STATUS '+json.dumps(value)))

    def test_live_platform_and_calculation_progress_are_distinguished_without_invented_percentage(self):
        binding=dict(kernel='example/job',material='Crystal',next_target='Audit result')
        now=time.time();telemetry=dict(updated_UTC=datetime.fromtimestamp(now,timezone.utc).isoformat(),status='computing',iteration=9,cutoffs_Ry=[130,720],SCF_target_Ry=1e-14)
        record=dict(connection='connected',checked_at=now,platform_status='RUNNING',telemetry=telemetry)
        state=snapshot(binding,record,now)
        self.assertTrue(state['active']);self.assertIn('130/720 Ry',state['current']);self.assertIn('iteration 9',state['metrics']);self.assertIsNone(state['percent'])
        record['checked_at']=now+300
        state=snapshot(binding,record,now+300)
        self.assertTrue(state['active']);self.assertIn('waiting for calculation update',state['current']);self.assertFalse(state['telemetry_fresh'])
        with patch('jobs.alive',side_effect=AssertionError('Never check a remote PID locally')):
            state=snapshot(binding,dict(connection='auth_required',telemetry=telemetry),now)
            self.assertFalse(state['active']);self.assertEqual(state['current'],'Kaggle connection required')
        record.update(platform_status='COMPLETE',checked_at=now)
        terminal=snapshot(binding,record,now+3600)
        self.assertEqual(terminal['snapshot_status'],'recorded');self.assertFalse(terminal['active'])
        self.assertIn('result audit required',terminal['current'])


if __name__=='__main__':unittest.main()
