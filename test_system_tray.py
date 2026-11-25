import queue
import threading
import unittest
from unittest.mock import patch
from worddict import system_tray as st

class SelectionWorkerTests(unittest.TestCase):
    def make_worker(self):
        with patch.object(st.cfg, 'get', return_value={'popup': {'enabled': True}}):
            return st.SystemThread(queue.Queue(), '')

    def test_idle_does_not_copy(self):
        worker = self.make_worker()
        def wait(timeout):
            worker._stop_event.set()
            return False
        with patch.object(worker._sel_event, 'wait', side_effect=wait), patch.object(st, '_send_ctrl_c') as copy:
            worker._selection_worker()
        copy.assert_not_called()

    def test_paused_does_not_copy(self):
        worker = self.make_worker()
        worker._paused = True
        def wait(timeout):
            if worker._sel_event.is_set():
                return True
            worker._stop_event.set()
            return False
        worker._sel_event.set()
        with patch.object(worker._sel_event, 'wait', side_effect=wait), patch.object(st, '_send_ctrl_c') as copy:
            worker._selection_worker()
        copy.assert_not_called()

    def test_thread_can_join(self):
        worker = self.make_worker()
        with patch.object(st.SystemThread, 'run', return_value=None):
            worker.start()
            worker.join(timeout=2)
        self.assertFalse(worker.is_alive())

if __name__ == '__main__':
    unittest.main()
