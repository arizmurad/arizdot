import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from activation import request,acknowledged,Inbox,caller_thread
from navigation import Navigation
from control import start

A='00000000-0000-4000-8000-000000000101'
B='00000000-0000-4000-8000-000000000102'


class ActivationTests(unittest.TestCase):
    def test_calling_chat_not_current_directory_defines_context(self):
        with patch.dict(os.environ,{'CODEX_THREAD_ID':B}):
            self.assertEqual(caller_thread(),B)
            self.assertEqual(caller_thread(A),A)

    def test_request_needs_matching_acknowledgement(self):
        with tempfile.TemporaryDirectory() as tmp:
            value=request(B,tmp);inbox=Inbox(tmp)
            self.assertEqual(inbox.poll()['thread'],B)
            self.assertIsNone(inbox.poll())
            self.assertIsNone(acknowledged(value,tmp))
            inbox.ack(value,B)
            self.assertEqual(acknowledged(value,tmp)['thread_id'],B)
            other=request(A,tmp)
            self.assertIsNone(acknowledged(other,tmp))

    def test_expired_requests_do_not_reactivate_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            value=request(A,tmp);value['created']=time.time()-60
            (Path(tmp)/'activation-request.json').write_text(json.dumps(value))
            self.assertIsNone(Inbox(tmp).poll())

    def test_explicit_invocation_wins_until_user_navigates_again(self):
        n=Navigation([])
        n.consume(f'2026-01-01T00:00:00.000Z browser sidebar owner sync ownerRoutePath=/local/{A}\n')
        n.activate(B)
        self.assertEqual(n.poll(),B)
        n.consume(f'2099-01-01T00:00:00.000Z browser sidebar owner sync ownerRoutePath=/local/{A}\n')
        self.assertEqual(n.poll(),A)

    def test_running_window_alone_is_not_activation_success(self):
        with patch('control.running',return_value=True),patch('activation.request',return_value={'id':'a'}),patch('activation.acknowledged',return_value=None),patch('control.time.monotonic',side_effect=[0,7]):
            result=start()
        self.assertTrue(result['running'])
        self.assertFalse(result['activated'])

    def test_status_process_restores_the_ui_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            (path/'activation-ack.json').write_text(json.dumps(dict(thread_id=B,acknowledged=time.time())))
            with patch('activation.ROOT',path):n=Navigation()
            n.roots=[]
            self.assertEqual(n.poll(),B)


if __name__=='__main__':unittest.main()
