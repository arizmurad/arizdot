import tempfile
import time
import unittest
from pathlib import Path
from alerts import AlertPolicy
from health import classify
from pulse import State


def job(**values):
    value=dict(title='TlInS₂',case='old_w130',phase='computing',badge='RUN',snapshot_status='live',finished_count=4,health='CPU aktiv')
    value.update(values)
    return value


class HealthTests(unittest.TestCase):
    def test_cpu_advancing_keeps_silent_log_live(self):
        self.assertEqual(classify(job(output_age_seconds=900),.7),'live')
        self.assertEqual(classify(job(output_age_seconds=900),0),'stale')

    def test_memory_wait_requires_recent_controller_update(self):
        self.assertEqual(classify(job(phase='waiting_memory',controller_updated_seconds=2)),'live')
        self.assertEqual(classify(job(phase='waiting_memory',controller_updated_seconds=200)),'stale')

    def test_missing_worker_and_unreadable_source_are_offline(self):
        self.assertEqual(classify(job(badge='STOP')),'offline')
        self.assertEqual(classify(job(source_error=True)),'offline')

    def test_intentional_stop_is_recorded_not_a_connection_failure(self):
        self.assertEqual(classify(job(phase='stopped_by_user',badge='STOP')),'recorded')

    def test_frozen_reader_degrades_without_fresh_disk_reads(self):
        s=State(background=job(active=True),observed_at=time.monotonic()-12)
        self.assertEqual(s.freshness,'stale')
        s.observed_at=time.monotonic()-40
        self.assertEqual(s.freshness,'offline')
        self.assertFalse(s.working)


class AlertTests(unittest.TestCase):
    def policy(self,tmp):return AlertPolicy(Path(tmp)/'notifications.json',wait_seconds=600)

    def test_startup_is_silent_then_completion_fires_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.policy(tmp)
            self.assertEqual(p.observe('thread',job(phase='completed'),1000),[])
            p.observe('thread',job(),1001)
            done=job(badge='CHECK')
            self.assertEqual(len(p.observe('thread',done,1002)),1)
            self.assertEqual(p.observe('thread',done,1003),[])
            q=self.policy(tmp)
            q.observe('thread',job(),1004)
            self.assertEqual(q.observe('thread',done,1005),[])

    def test_wait_alert_once_after_ten_minutes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.policy(tmp)
            waiting=job(phase='waiting_memory',badge='WAIT')
            self.assertEqual(p.observe('thread',waiting,1000),[])
            self.assertEqual(p.observe('thread',waiting,1599),[])
            self.assertEqual(len(p.observe('thread',waiting,1600)),1)
            self.assertEqual(p.observe('thread',waiting,2000),[])
            q=self.policy(tmp)
            self.assertEqual(q.observe('thread',waiting,2100),[])

    def test_transient_failure_does_not_notify(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.policy(tmp)
            bad=job(snapshot_status='offline',badge='STOP')
            self.assertEqual(p.observe('thread',bad,1000),[])
            self.assertEqual(p.observe('thread',bad,1005),[])
            p.observe('thread',job(),1006)
            self.assertEqual(p.observe('thread',bad,1007),[])
            self.assertEqual(len(p.observe('thread',bad,1017)),1)
            self.assertEqual(p.observe('thread',bad,1030),[])

    def test_muted_events_are_not_replayed_after_unmuting(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.policy(tmp)
            p.observe('thread',job(),1000)
            p.enable(False)
            self.assertEqual(p.observe('thread',job(badge='CHECK'),1001),[])
            p.enable(True)
            self.assertEqual(p.observe('thread',job(badge='CHECK'),1002),[])

    def test_case_transition_without_check_record_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.policy(tmp)
            p.observe('thread',job(),1000)
            self.assertEqual(len(p.observe('thread',job(case='old_w140',finished_count=5),1002)),1)


if __name__=='__main__':unittest.main()
