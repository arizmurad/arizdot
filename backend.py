"""Keep session and job disk reads off the animation thread."""
import copy
import threading
import time


class AsyncMonitor:
    def __init__(self,monitor):
        from pulse import State
        self.monitor=monitor
        self.snapshot=(State(),0,'')
        self.stop=threading.Event()
        self.tasks=[]
        self.requested_thread=None
        self.worker=threading.Thread(target=self.run,daemon=True,name='arizdot-status')
        self.worker.start()
        self.tasks_worker=None
        if hasattr(monitor,'collect_tasks'):
            self.tasks_worker=threading.Thread(target=self.collect,daemon=True,name='arizdot-tasks')
            self.tasks_worker.start()

    def run(self):
        while not self.stop.is_set():
            try:
                requested=self.requested_thread
                if requested:
                    self.requested_thread=None
                    self.monitor.navigation.activate(requested)
                    self.monitor.last_poll=-10
                value=copy.deepcopy(self.monitor.poll())
                if hasattr(value[0],'observed_at'):value[0].observed_at=time.monotonic()
                self.snapshot=value
            except (OSError,ValueError,TypeError):pass
            self.stop.wait(.5)

    def collect(self):
        # This collector owns separate tails: slow transcripts cannot delay
        # explicit activation of a Claude conversation in the primary reader.
        while not self.stop.is_set():
            try:
                entries=copy.deepcopy(self.monitor.collect_tasks())
                now=time.monotonic()
                for state,_ in entries:state.observed_at=now
                self.tasks=entries
            except (OSError,ValueError,TypeError):pass
            self.stop.wait(1)

    def poll(self):return self.snapshot
    def panel_snapshot(self):return (*self.snapshot,self.tasks)
    def follow_thread(self,thread):self.requested_thread=thread
    @property
    def notifications_enabled(self):return False
    def poll_alerts(self):return []
    def watchdog(self):return []
    def close(self):self.stop.set()
