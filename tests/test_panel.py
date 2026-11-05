import tempfile
import json
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from pulse import State
from panel import PanelModel,PanelPainter,ROW,HEADER,DETAIL
from surface import WIDTH,MAX_HEIGHT
from backend import AsyncMonitor
from claude_support import report_desktop,snapshot_state

A='00000000-0000-4000-8000-000000000201'
B='00000000-0000-4000-8000-000000000202'


def work(ref,title):
    return State(title=title,active=True,stage='Checking results',session_ref=ref,source_modified=time.time(),
        plan=[dict(step='Read inputs',status='completed'),dict(step='Check results',status='in_progress'),dict(step='Write report',status='pending')])


class PanelTests(unittest.TestCase):
    def test_parallel_tasks_keep_distinct_progress_and_selected_steps(self):
        a=work(A,'Material A');b=work(B,'Material B')
        b.plan[0]['status']='pending'
        model=PanelModel();model.update(a,A,[(a,Path(A)),(b,Path(B))],'en')
        self.assertEqual(len(model.cards),2)
        self.assertEqual([c.percent for c in model.cards],[33,0])
        model.toggle(B)
        self.assertEqual(model.expanded,B)
        painter=PanelPainter()
        lines=painter.detail_lines(model.visible[1],'en')
        self.assertIn(('No completed steps recorded',False,'#d6dae3'),lines)
        self.assertIn('Read inputs',' '.join(line[0] for line in lines))
        model.update(a,A,[(b,Path(B)),(a,Path(A))],'en')
        self.assertEqual([c.ref for c in model.cards],[A,B])
        self.assertEqual(model.expanded,B)

    def test_header_dot_and_detail_body_do_not_toggle_a_task(self):
        a=work(A,'Task');model=PanelModel();model.update(a,A,[],'en');model.toggle(A)
        layout=model.layout()
        self.assertIsNone(layout.hit(WIDTH/2,16))
        self.assertEqual(layout.hit(30,HEADER+10),A)
        self.assertIsNone(layout.hit(30,HEADER+ROW+10))
        self.assertEqual(layout.height,HEADER+ROW+DETAIL+28)

    def test_reported_concurrent_work_is_visible_but_never_claimed_observed(self):
        with tempfile.TemporaryDirectory() as tmp:
            steps=[dict(step='Analyze',status='completed'),dict(step='Write',status='in_progress'),dict(step='Review',status='pending')]
            report_desktop(B,'Claude task','Writing',steps=steps,root=tmp)
            b=snapshot_state(B,'claude-desktop',tmp)
            a=work(A,'Codex task');model=PanelModel()
            model.update(a,A,[(b,Path(B))],'en')
            self.assertEqual(len(model.cards),2)
            self.assertFalse(model.cards[1].working)
            self.assertTrue(model.cards[1].reported)
            self.assertEqual(model.cards[1].completed,('Analyze',))
            self.assertEqual(model.cards[1].percent,33)

    def test_ended_and_old_chats_do_not_fill_the_concurrent_list(self):
        a=work(A,'Selected');b=work(B,'Old active marker');b.source_modified=time.time()-3600
        model=PanelModel();model.update(a,A,[(b,Path(B))],'en')
        self.assertEqual(len(model.cards),1)
        a.active=False;model.update(a,A,[],'en')
        self.assertEqual(model.cards[0].ref,A)

    def test_scroll_keeps_all_tasks_reachable_and_no_fabricated_done_steps(self):
        states=[work(str(i),'Task '+str(i)) for i in range(6)]
        model=PanelModel();model.update(states[0],'0',[(s,Path(s.session_ref)) for s in states],'az')
        model.scroll(3)
        self.assertEqual([c.ref for c in model.visible],['3','4','5'])
        model.toggle('5');model.scroll(-3)
        self.assertIsNone(model.expanded)

    def test_panel_images_fit_native_buffer_and_keep_antialiasing(self):
        a=work(A,'TaInS₂ · SCF');b=work(B,'A second task')
        model=PanelModel();model.update(a,A,[(b,Path(B))],'az');model.toggle(B)
        painter=PanelPainter()
        for progress in (0,.25,.75,1):
            for reveal in (0,.5,1):
                image=painter.draw_panel(model,progress,reveal,12,'az')
                self.assertEqual(image.width,WIDTH)
                self.assertLessEqual(image.height,MAX_HEIGHT)
                self.assertGreater(len(set(image.getchannel('A').tobytes())),20)


class CollectorTests(unittest.TestCase):
    def test_slow_concurrent_reader_does_not_delay_primary_activation(self):
        blocked=threading.Event();release=threading.Event()
        class Navigation:
            def activate(self,ref):self.ref=ref
        class Reader:
            navigation=Navigation()
            def poll(self):return State(session_ref=getattr(self.navigation,'ref',A)),1,getattr(self.navigation,'ref',A)
            def collect_tasks(self):blocked.set();release.wait(2);return []
        monitor=AsyncMonitor(Reader())
        try:
            self.assertTrue(blocked.wait(1))
            monitor.follow_thread(B)
            deadline=time.monotonic()+1.2
            while monitor.poll()[2]!=B and time.monotonic()<deadline:time.sleep(.02)
            self.assertEqual(monitor.poll()[2],B)
            self.assertEqual(monitor.poll_alerts(),[])
            self.assertFalse(monitor.notifications_enabled)
        finally:release.set();monitor.close()

    def test_collector_reads_both_providers_without_switching_primary(self):
        from providers import MultiMonitor
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sessions=root/'sessions';sessions.mkdir()
            (sessions/(A+'.jsonl')).write_text(json.dumps(dict(type='event_msg',payload=dict(type='task_started')))+'\n')
            report_desktop(B,'Claude work','Writing',root=root)
            with patch('providers.ROOT',root),patch('providers.snapshot_state',side_effect=lambda sid,provider:snapshot_state(sid,provider,root)):
                monitor=MultiMonitor(sessions,'claude-desktop:'+B)
                rows=monitor.collect_tasks()
                self.assertEqual({s.session_ref for s,p in rows},{A,'claude-desktop:'+B})
                self.assertEqual(monitor.navigation.selected,'claude-desktop:'+B)


if __name__=='__main__':unittest.main()
