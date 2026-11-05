import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from observations import cloud_snapshot
from jobs import Jobs


class ObservationTests(unittest.TestCase):
    def test_old_cloud_data_is_not_claimed_as_live_or_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'cloud.json'
            p.write_text(json.dumps(dict(observed_UTC=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat(),status='computing',qe_pid=4473,case='bridge_w130_r560_k221',iteration=6,last_scf_error_Ry=3e-8,target_Ry=1e-10)))
            s=cloud_snapshot(p,'TlInS₂')
            self.assertEqual(s['snapshot_status'],'stale')
            self.assertFalse(s['active'])
            self.assertNotIn('pid',s)
            self.assertEqual(s['remote_pid'],4473)
            self.assertIsNone(s['percent'])
            self.assertIn('SCF 6',s['metrics'])

    def test_recent_cloud_observation_is_still_recorded_not_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'cloud.json';p.write_text(json.dumps(dict(observed_UTC=datetime.now(timezone.utc).isoformat())))
            self.assertEqual(cloud_snapshot(p)['snapshot_status'],'recorded')

    def test_cloud_migration_does_not_read_stopped_local_controller(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            project=root/'project.json';project.write_text(json.dumps(dict(status='Colab_bridge_computing')))
            cloud=root/'cloud.json';cloud.write_text(json.dumps(dict(observed_UTC=datetime.now(timezone.utc).isoformat())))
            config=root/'config.json';config.write_text(json.dumps({'thread':dict(adapter='qe',root='missing-local',project_state=str(project),cloud_observation=str(cloud))}))
            with patch('jobs.qe_snapshot',side_effect=AssertionError('Local controller must not be read')):
                value=Jobs(config).get('thread')
            self.assertTrue(value['observation'])


if __name__=='__main__':unittest.main()
