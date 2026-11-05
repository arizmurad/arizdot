import threading
import time
import unittest
from backend import AsyncMonitor


class BackendTests(unittest.TestCase):
    def test_slow_disk_reader_does_not_block_animation(self):
        started=threading.Event()
        release=threading.Event()
        class Slow:
            def poll(self):
                started.set()
                release.wait(1)
                return ('ready',1,'id')
        monitor=AsyncMonitor(Slow())
        try:
            self.assertTrue(started.wait(1))
            # If poll touches the reader this call blocks on release.
            before=time.monotonic()
            for _ in range(1000):monitor.poll()
            self.assertLess(time.monotonic()-before,.1)
        finally:
            release.set()
            monitor.close()

    def test_snapshot_is_independent_of_mutable_reader(self):
        shared={'count':1}
        class Reader:
            def poll(self):return (shared,0,'id')
        monitor=AsyncMonitor(Reader())
        monitor.worker.join(.03)
        monitor.close()
        value=monitor.poll()
        shared['count']=2
        self.assertEqual(value[0]['count'],1)


if __name__=='__main__':unittest.main()
