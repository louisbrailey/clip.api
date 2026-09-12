import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).parents[1]
loader=importlib.util.spec_from_file_location('render_runtime',ROOT/'worker/runtime.py');r=importlib.util.module_from_spec(loader);loader.loader.exec_module(r)
JID='65738378-9192-4d02-94bb-28c8a966f7f4';LEASE='1c2cc62b-bdf3-479c-aad0-3c7df2032741';ASSET='6cb9f125-4710-42a0-ad30-92f14b1c4caf'
SPEC={'seconds':10,'noise':'pink','theme':'ocean','seed':123}
DATA=b'\x00\x00\x00\x18ftypisom'+b'original fixture'*20
DIGEST=hashlib.sha256(DATA).hexdigest()
def context():return {'job':{'id':JID,'lease':LEASE,'kind':'render','mode':'live','approved':1,'lane':'ambient','render_spec':json.dumps(SPEC)}}
def fixture(output,spec,valid):
    output.write_bytes(DATA);output.with_suffix('.rights.json').write_text(json.dumps({'rights':'original','sha256':DIGEST,'duration_seconds':10}))

class RenderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.journal=r.Journal(self.temp.name);self.portal=Mock();self.portal.call.return_value={'ok':True,'asset':None};self.portal.render_output.return_value={'asset':ASSET,'sha256':DIGEST}
        self.render=patch.object(r,'render_process',side_effect=fixture).start();self.addCleanup(patch.stopall)
    def run_task(self,c=None,valid=lambda:True):return r.render_ambient(c or context(),self.portal,valid,self.journal)
    def test_render_and_transfer_match_original_provenance(self):
        result=self.run_task();self.assertEqual(result['receipt'],'asset:'+ASSET);self.assertEqual(result['tokens'],0)
        self.portal.render_output.assert_called_once_with(JID,LEASE,DATA,DIGEST);self.assertEqual(self.portal.call.call_count,2)
        self.assertFalse(self.render.call_args.args[0].exists())
    def test_invalid_recipes_never_start_process(self):
        for spec in [dict(SPEC,seconds=301),dict(SPEC,seconds=True),dict(SPEC,seed=0),dict(SPEC,noise='pink;curl evil'),dict(SPEC,theme='https://evil'),dict(SPEC,source='/private/file'),[]]:
            c=context();c['job']['render_spec']=json.dumps(spec)
            with self.assertRaises(r.RuntimeFailure):self.run_task(c)
        self.render.assert_not_called();self.portal.call.assert_not_called()
    def test_unapproved_and_other_tasks_do_not_render(self):
        for field,value in [('approved',0),('kind','draft'),('mode','rehearsal'),('lane','sports')]:
            c=context();c['job'][field]=value
            with self.assertRaises(r.RuntimeFailure):self.run_task(c)
        self.render.assert_not_called()
    def test_preflight_denial_does_not_render(self):
        self.portal.call.side_effect=r.RuntimeFailure('paused')
        with self.assertRaises(r.RuntimeFailure):self.run_task()
        self.render.assert_not_called()
    def test_lost_lease_before_render(self):
        with self.assertRaises(r.RuntimeFailure):self.run_task(valid=lambda:False)
        self.render.assert_not_called()
    def test_lost_lease_after_render_prevents_transfer(self):
        valid=Mock(side_effect=[True,False])
        with self.assertRaises(r.RuntimeFailure):self.run_task(valid=valid)
        self.portal.render_output.assert_not_called()
    def test_pause_after_render_prevents_transfer(self):
        self.portal.call.side_effect=[{'asset':None},r.RuntimeFailure('paused')]
        with self.assertRaises(r.RuntimeFailure):self.run_task()
        self.portal.render_output.assert_not_called()
    def test_saved_asset_recovery_does_not_render_or_upload(self):
        self.portal.call.return_value={'asset':ASSET,'sha256':DIGEST}
        self.assertEqual(self.run_task()['receipt'],'asset:'+ASSET)
        self.render.assert_not_called();self.portal.render_output.assert_not_called()
    def test_lost_upload_response_recovers_one_canonical_asset(self):
        self.portal.render_output.side_effect=r.RuntimeFailure('lost upload response')
        with self.assertRaises(r.RuntimeFailure):self.run_task()
        self.portal.call.return_value={'asset':ASSET,'sha256':DIGEST}
        self.assertEqual(self.run_task()['receipt'],'asset:'+ASSET);self.assertEqual(self.render.call_count,1)
    def test_stale_local_receipt_cannot_override_portal_binding(self):
        self.journal.write(JID,{'phase':'recorded','status':'succeeded','receipt':'asset:untrusted'})
        self.portal.call.return_value={'asset':ASSET,'sha256':DIGEST}
        self.assertEqual(self.run_task()['receipt'],'asset:'+ASSET)
    def test_digest_mismatch_prevents_transfer(self):
        def corrupt(output,spec,valid):
            fixture(output,spec,valid);output.write_bytes(DATA+b'changed')
        self.render.side_effect=corrupt
        with self.assertRaises(r.RuntimeFailure):self.run_task()
        self.portal.render_output.assert_not_called()
    def test_missing_mp4_prevents_transfer(self):
        self.render.side_effect=lambda output,spec,valid:None
        with self.assertRaises(r.RuntimeFailure):self.run_task()
        self.portal.render_output.assert_not_called()
    def test_invalid_saved_receipt_cannot_succeed(self):
        self.portal.call.return_value={'asset':'https://evil.example','sha256':DIGEST}
        with self.assertRaises(r.RuntimeFailure):self.run_task()
    def test_worker_uses_renderer_without_model_provider(self):
        with patch.object(r,'run_model') as model:r.Worker(self.portal,self.journal).process(context())
        model.assert_not_called();self.assertEqual(self.journal.read(JID)['status'],'succeeded')
    def test_transfer_stays_on_configured_portal(self):
        with patch.dict(os.environ,{'SITES_API_TOKEN':'fixture-sites-token-value'},clear=True),patch.object(r,'json_http',return_value=({'asset':ASSET,'sha256':DIGEST},{},200)) as send:
            portal=r.Portal('https://portal.example','cs_'+'a'*64);portal.render_output(JID,LEASE,DATA,DIGEST)
        self.assertEqual(send.call_args.args[0],'https://portal.example/api/render')
        self.assertEqual(send.call_args.kwargs['headers']['OAI-Sites-Authorization'],'Bearer fixture-sites-token-value')
        self.assertNotIn(b'fixture-sites-token-value',send.call_args.kwargs['body'])

class ProcessTests(unittest.TestCase):
    def test_renderer_environment_omits_credentials(self):
        process=Mock();process.poll.return_value=0;process.returncode=0
        with patch.dict(os.environ,{'OPENAI_API_KEY':'private','SITES_API_TOKEN':'private','X_AMBIENT':'private','PATH':'/usr/bin'},clear=True),patch.object(r.subprocess,'Popen',return_value=process) as start:
            r.render_process(Path('/tmp/original.mp4'),SPEC,lambda:True)
        self.assertEqual(start.call_args.kwargs['env'],{'PATH':'/usr/bin'});self.assertNotIn('shell',start.call_args.kwargs)
        self.assertNotIn('--source',start.call_args.args[0])
    def test_lease_loss_terminates_renderer_process_group(self):
        process=Mock();process.poll.return_value=None;process.pid=12345
        with patch.object(r.subprocess,'Popen',return_value=process),patch.object(r.os,'killpg') as kill:
            with self.assertRaises(r.RuntimeFailure):r.render_process(Path('/tmp/original.mp4'),SPEC,lambda:False)
        kill.assert_called_once_with(12345,r.signal.SIGTERM);process.wait.assert_called_once()

if __name__=='__main__':unittest.main()
