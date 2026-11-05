import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from pathlib import Path
from island import Island
from panel import PanelModel
from tests.test_panel import work,A,B


class ClickTests(unittest.TestCase):
    def island(self):
        app=Island.__new__(Island)
        app.root=Mock();app.root.winfo_y.return_value=10
        app.canvas=Mock();app.anchor=960;app.click_timer=None;app.drag=None
        app.expand_target=None;app.press_target=None;app.last_paint=None
        app.click_reference=None;app.click_position=None;app.click_started=0
        app.panel=PanelModel();a=work(A,'A');b=work(B,'B')
        app.panel.update(a,A,[(b,Path(B))],'en')
        app.layout=app.panel.layout()
        app.morph=Mock();app.morph.value.return_value=1
        app.visible_thread=A
        return app

    def event(self,x,y):return SimpleNamespace(x=x,y=y,x_root=x+755,y_root=y+10)

    def test_dot_click_has_no_popup_but_row_click_expands_only_that_task(self):
        app=self.island()
        dot=self.event(205,16);app.press(dot);app.release(dot)
        app.root.after.assert_not_called()
        row=self.event(30,130);app.press(row);app.release(row)
        app.root.after.call_args.args[1]()
        self.assertEqual(app.panel.expanded,B)
        self.assertIsNone(app.drag)

    def test_double_click_returns_to_the_clicked_task_and_cancels_single_click(self):
        app=self.island();row=self.event(30,130)
        app.press(row);app.release(row)
        with patch('navigation.open_thread',return_value={'exact':True}) as launch:app.open_chat(row)
        launch.assert_called_once_with(B)
        app.root.after_cancel.assert_called_once()
        self.assertIsNone(app.expand_target)

    def test_closing_cancels_a_delayed_row_click(self):
        app=self.island();row=self.event(30,130)
        app.press(row);app.release(row)
        app.expand_target=B
        app.collapse_subprocess()
        app.root.after_cancel.assert_called_once()
        self.assertIsNone(app.click_timer)
        self.assertIsNone(app.expand_target)

    def test_double_click_in_subprocess_body_uses_that_tasks_reference(self):
        app=self.island();app.panel.expanded=B;app.expand_target=B;app.layout=app.panel.layout()
        with patch('navigation.open_thread',return_value={'exact':True}) as launch:
            app.open_chat(self.event(30,260))
        launch.assert_called_once_with(B)

    def test_double_click_keeps_original_task_after_a_different_subprocess_collapses(self):
        app=self.island();app.panel.expanded=A;app.expand_target=A;app.layout=app.panel.layout()
        row=self.event(30,360);app.press(row);app.release(row)
        app.root.after.call_args.args[1]();app.layout=app.panel.layout()
        self.assertEqual(app.panel.expanded,B)
        with patch('navigation.open_thread',return_value={'exact':True}) as launch:app.open_chat(row)
        launch.assert_called_once_with(B)


@unittest.skipUnless(os.name=='nt' and os.environ.get('ARIZDOT_NATIVE_TEST')=='1','Opt-in native desktop verification')
class NativeTests(unittest.TestCase):
    def test_native_double_click_in_mixed_provider_subprocess_opens_its_chat(self):
        a=work(A,'Codex task');ref='claude:'+B;b=work(ref,'Claude task')
        class Reader:
            def panel_snapshot(self):return a,2,A,[(a,Path(A)),(b,Path(B))]
        def pump(app,seconds):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:app.root.update();time.sleep(.005)
        with patch('activation.Inbox.poll',return_value=None),patch('navigation.open_thread',return_value={'exact':True}) as launch:
            app=Island(Reader())
            try:
                with patch.object(app.root,'winfo_pointerxy',return_value=(app.center(),26)) as pointer:
                    pump(app,.5);app.toggle_task(ref);pump(app,.4)
                    pointer.return_value=(app.center(),270)
                    for stamp in (1000,1100):
                        app.canvas.event_generate('<ButtonPress-1>',x=30,y=260,time=stamp)
                        app.canvas.event_generate('<ButtonRelease-1>',x=30,y=260,time=stamp+20)
                        app.root.update()
                    launch.assert_called_once_with(ref)
            finally:app.root.destroy();app.surface.close()

    def test_mixed_provider_click_survives_primary_switch_and_completion(self):
        a=work(A,'Codex task');ref='claude:'+B;b=work(ref,'Claude task')
        class Reader:
            primary=A
            def panel_snapshot(self):
                selected=a if self.primary==A else b
                return selected,2,self.primary,[(a,Path(A)),(b,Path(B))]
        reader=Reader()
        def pump(app,seconds):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:app.root.update();time.sleep(.005)
        with patch('activation.Inbox.poll',return_value=None):
            app=Island(reader)
            try:
                with patch.object(app.root,'winfo_pointerxy',return_value=(app.center(),26)) as pointer:
                    pump(app,.5)
                    pointer.return_value=(app.center(),150)
                    app.canvas.event_generate('<ButtonPress-1>',x=40,y=140)
                    reader.primary=ref;app.last_model=-10
                    pump(app,.12)
                    app.canvas.event_generate('<ButtonRelease-1>',x=40,y=140)
                    pump(app,.4)
                    self.assertEqual(app.panel.expanded,ref)
                    self.assertEqual([row[0] for row in app.layout.rows],[A,ref])
                    reader.primary=A;b.active=False;b.status='Cavab hazırdır'
                    for step in b.plan:step['status']='completed'
                    app.last_model=-10;pump(app,.6)
                    self.assertEqual(app.panel.expanded,ref)
                    self.assertEqual(app.panel.visible[1].percent,100)
            finally:app.root.destroy();app.surface.close()

    def test_leaving_closes_subprocesses_and_each_hover_starts_with_task_list(self):
        a=work(A,'Native test A');b=work(B,'Native test B')
        class Reader:
            def panel_snapshot(self):return a,2,A,[(a,Path(A)),(b,Path(B))]
        def pump(app,seconds):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:app.root.update();time.sleep(.005)
        with patch('activation.Inbox.poll',return_value=None):
            app=Island(Reader())
            try:
                with patch.object(app.root,'winfo_pointerxy',return_value=(app.center(),26)) as pointer:
                    # Explicit activation may hold the panel open until the first
                    # pointer visit, but must not pin it after the user leaves.
                    app.forced_open_until=time.monotonic()+3
                    for _ in range(2):
                        pointer.return_value=(app.center(),26)
                        pump(app,.5)
                        self.assertGreater(app.morph.position,.98)
                        self.assertIsNone(app.panel.expanded)
                        app.toggle_task(B)
                        pump(app,.4)
                        self.assertEqual(app.panel.expanded,B)
                        # Moving down into the revealed subprocess is still
                        # inside the panel and must leave it readable.
                        top,bottom=app.layout.details
                        pointer.return_value=(app.center(),10+int((top+bottom)/2))
                        pump(app,.12)
                        self.assertEqual(app.expand_target,B)
                        pointer.return_value=(0,900)
                        pump(app,.85)
                        self.assertLess(app.morph.position,.002)
                        self.assertIsNone(app.expand_target)
                        self.assertIsNone(app.panel.expanded)
            finally:app.root.destroy();app.surface.close()

    def test_native_surface_inline_animation_and_no_secondary_window(self):
        a=work(A,'Native test A');b=work(B,'Native test B')
        class Reader:
            def panel_snapshot(self):return a,2,A,[(a,Path(A)),(b,Path(B))]
        with patch('island.Island.open_reference') as launch,patch('activation.Inbox.poll',return_value=None):
            app=Island(Reader())
            try:
                app.forced_open_until=time.monotonic()+3
                deadline=time.monotonic()+.5
                while time.monotonic()<deadline:app.root.update();time.sleep(.005)
                app.toggle_task(B)
                deadline=time.monotonic()+.4
                while time.monotonic()<deadline:app.root.update();time.sleep(.005)
                self.assertEqual(app.panel.expanded,B)
                self.assertGreater(app.layout.details[1]-app.layout.details[0],200)
                self.assertEqual([c.winfo_class() for c in app.root.winfo_children()],['Canvas'])
                self.assertEqual(len(app.panel.visible),2)
                app.open_chat(SimpleNamespace(x=30,y=130))
                launch.assert_called_once_with(B)
                app.toggle_task(B)
                deadline=time.monotonic()+.4
                while time.monotonic()<deadline:app.root.update();time.sleep(.005)
                self.assertIsNone(app.panel.expanded)
                self.assertIsNone(app.layout.details)
            finally:app.root.destroy();app.surface.close()


if __name__=='__main__':unittest.main()
