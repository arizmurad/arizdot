import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from background_jobs import Store,Monitor,observe,state_for,validate_source,SameOriginRedirect
from job_signal import JobSignal
from panel import PanelModel,PanelPainter
from pulse import State

A='00000000-0000-4000-8000-000000000941'
B='00000000-0000-4000-8000-000000000942'


class BackgroundJobTests(unittest.TestCase):
    def test_managed_launch_registers_and_tracks_a_real_child_after_the_launcher_returns(self):
        import sys
        from background_launch import launch
        with tempfile.TemporaryDirectory() as tmp:
            result=launch(A,dict(title='Synthetic background export',command=[sys.executable,'-c','import time; time.sleep(1.5)'],cwd=tmp),tmp)
            self.assertTrue(result['launched']);self.assertTrue(result['pid'])
            job=Store(tmp).list()[0];self.assertEqual(job['id'],result['job_id'])
            running=observe(job);self.assertIn(running['phase'],('running','completed'))
            deadline=time.monotonic()+6
            while time.monotonic()<deadline:
                final=observe(job)
                if final['phase']=='completed':break
                time.sleep(.1)
            self.assertEqual(final['phase'],'completed');self.assertIsNone(final['percent'])
            self.assertIn('verify outputs',final['current'])
    def test_independent_file_job_updates_after_reply_and_across_provider_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=Store(root);jobs=[]
            for owner in (A,'claude:'+B,'claude-desktop:'+B):
                path=root/(str(len(jobs))+'.json');signal=JobSignal(path,'run-'+str(len(jobs)))
                signal.write('running','Initial operation',completed=0,total=4)
                job=store.register(owner,'Real background work',dict(type='json_file',path=str(path)),signal.run_id)
                jobs.append((job,signal))
            monitor=Monitor(root,start=False);monitor.refresh()
            model=PanelModel();chat=State(active=False,stage='Reply ready')
            model.update(chat,A,monitor.collect(),'en')
            ref='job:'+jobs[0][0]['id'];model.toggle(ref)
            for job,signal in jobs:signal.write('running','New calculation stage',completed=2,total=4,next_step='Verify outputs')
            monitor.refresh();model.update(chat,A,monitor.collect(),'en',preserve_order=True)
            cards=[c for c in model.cards if c.ref.startswith('job:')]
            self.assertEqual(len(cards),3);self.assertTrue(all(c.percent==50 for c in cards))
            self.assertTrue(all(c.current=='New calculation stage' for c in cards))
            self.assertEqual([c.provider for c in cards],['Codex','Claude','Claude'])
            self.assertEqual(model.expanded,ref)
            text=' '.join(v[0] for v in PanelPainter().detail_lines(cards[0],'en'))
            self.assertIn('50%',text);self.assertIn('Verify outputs',text)
            self.assertEqual(len(Store(root).list()),3)
            self.assertTrue(model.indicator_task.background_job)
            self.assertTrue(model.indicator_task.working)
            for job,signal in jobs:signal.write('running','Measured SCF work',metrics='Iteration 8; target 1e-14 Ry')
            monitor.refresh();rows=monitor.collect()
            model.update(chat,A,rows,'en',preserve_order=True)
            measured=next(c for c in model.cards if c.ref==ref)
            text=' '.join(v[0] for v in PanelPainter().detail_lines(measured,'en'))
            self.assertIn('Iteration 8',text);self.assertNotIn('milestone plan not reported',text)

    def test_deduplicates_registration_and_dismiss_does_not_touch_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);job=store.register(A,'Worker',dict(type='reported'),'run1')
            self.assertEqual(job['id'],store.register(A,'Worker',dict(type='reported'),'run1')['id'])
            store.update(job['id'],dict(state='running',current='Busy',completed=1,total=5),A)
            self.assertEqual(state_for(store.list()[0],observe(store.list()[0])).percent,20)
            with self.assertRaises(ValueError):store.update(job['id'],dict(state='completed'),'claude:'+A)
            self.assertFalse(store.dismiss(job['id'],A)['execution_changed']);self.assertFalse(store.list())

    def test_fast_source_refreshes_while_another_endpoint_is_slow(self):
        import threading
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp)
            slow=store.register(A,'Slow endpoint',dict(type='reported'),'slow')
            fast=store.register(A,'Fast endpoint',dict(type='reported'),'fast')
            blocked=threading.Event();release=threading.Event()
            def source(job):
                if job['id']==slow['id']:blocked.set();release.wait(2)
                return dict(phase='running',current=job['title'],source_updated=time.time(),checked_at=time.time())
            monitor=Monitor(tmp,start=False)
            with patch('background_jobs.observe',side_effect=source):
                worker=threading.Thread(target=monitor.refresh);worker.start()
                try:
                    self.assertTrue(blocked.wait(1));deadline=time.monotonic()+1
                    while fast['id'] not in monitor.cache and time.monotonic()<deadline:time.sleep(.01)
                    self.assertIn(fast['id'],monitor.cache);self.assertNotIn(slow['id'],monitor.cache)
                finally:release.set();worker.join(2)

    def test_https_adapter_contract_over_a_real_loopback_http_server(self):
        import threading
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body=json.dumps(dict(run_id='network-run',updated_at=time.time(),state='running',current='Remote work',completed=3,total=8)).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                job=Store(tmp).register(A,'HTTP job',dict(type='http_json',url=f'http://127.0.0.1:{server.server_port}/status'),'network-run')
                state=state_for(job,observe(job));self.assertEqual(state.current,'Remote work');self.assertEqual(state.percent,38)
        finally:server.shutdown();server.server_close();worker.join(2)

    def test_wrong_run_and_missing_source_never_show_old_progress_as_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'status.json';job=Store(tmp).register(A,'Calculation',dict(type='json_file',path=str(path)),'actual-run')
            JobSignal(path,'wrong-run').write('running','Unrelated calculation',completed=9,total=10)
            with self.assertRaises(ValueError):observe(job)
            state=state_for(job,error='mismatch');self.assertIsNone(state.percent)
            self.assertNotIn('Unrelated',state.current)
            signal=JobSignal(path,'actual-run');signal.write('completed','Verified result',completed=10,total=10)
            result=observe(job)
            with patch('background_jobs.time.time',return_value=time.time()+900):
                result['checked_at']=time.time();state=state_for(job,result)
                self.assertEqual(state.percent,100);self.assertEqual(state.background['phase'],'completed')

    def test_local_pid_creation_identity_prevents_adopting_a_recycled_process(self):
        with tempfile.TemporaryDirectory() as tmp,patch('background_jobs.process_identity',return_value='creation-one'):
            job=Store(tmp).register(A,'Local build',dict(type='process',pid=123),'run1')
        with patch('background_jobs.process_identity',return_value='creation-two'),patch('jobs.alive') as alive:
            value=observe(job)
            alive.assert_not_called();self.assertEqual(value['phase'],'unknown');self.assertIsNone(value['percent'])

    def test_transport_rejects_embedded_secrets_insecure_urls_and_cross_origin_redirects(self):
        for source in (dict(type='http_json',url='http://example.com/status'),dict(type='http_json',url='https://user:secret@example.com/status'),dict(type='json_file',path='../anything')):
            with self.assertRaises(ValueError):validate_source(source)
        from urllib.request import Request
        request=Request('https://example.com/status',headers={'Authorization':'Bearer private'})
        with self.assertRaises(ValueError):SameOriginRedirect().redirect_request(request,None,302,'',{},'https://other.example/status')

    def test_job_double_click_routes_to_owning_app_and_chat(self):
        from navigation import open_thread
        job=dict(id=A,owner='claude-desktop:'+B)
        with patch('background_jobs.Store.list',return_value=[job]),patch('claude_support.read_snapshot',return_value={'conversation_id':B}),patch('navigation.os.startfile',create=True) as launch:
            result=open_thread('job:'+A)
            self.assertTrue(result['exact']);launch.assert_called_once_with('claude://claude.ai/chat/'+B)


if __name__=='__main__':unittest.main()
