"""X provider fixtures; no requests leave the test process."""
import base64
import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import urllib.parse
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('x_runtime',Path(__file__).parents[1]/'worker/runtime.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
ACCOUNT={'platform':'x','external_id':'1234567890123456789','credential_ref':'X_FIXTURE','authorized':1}
CONFIG={'client_id':'fixture-client','client_secret':'fixture-secret','refresh_token':'seed-refresh'}
def context():
    return {'job':{'id':'x-fixture','lease':'fixture-lease','mode':'live','kind':'publish','approved':1,'asset':'fixture-media','title':'Internal title','brief':'Exact reviewed caption','made_with_ai':1},'account':dict(ACCOUNT)}

class Portal:
    def __init__(self):self.preflights=0;self.revoke_on=0;self.video=b'0000ftyp'+b'A'*(4*1024*1024)
    def media(self,asset):return self.video
    def call(self,action,**kwargs):
        assert action=='preflight';self.preflights+=1
        if self.preflights==self.revoke_on:raise r.RuntimeFailure('Publication paused')
        return {'ok':True}

class XUploadTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.journal=r.Journal(self.directory.name);self.portal=Portal();self.calls=[]
        self.token=patch.object(r.XCredentialStore,'token',return_value='fixture-access');self.token.start()
        self.reply={};self.statuses=[{'state':'pending','check_after_secs':1},{'state':'succeeded'}]
    def tearDown(self):self.token.stop();self.directory.cleanup()
    def provider(self,url,**kw):
        self.calls.append((url,kw))
        if url in self.reply:
            value=self.reply[url]
            if isinstance(value,Exception):raise value
            return value
        if url.endswith('/users/me'):data={'id':ACCOUNT['external_id']}
        elif url.endswith('/initialize'):data={'id':'99887766','expires_after_secs':86400}
        elif url.endswith('/append'):data={'expires_at':int(time.time())+86400}
        elif url.endswith('/finalize'):data={'id':'99887766','expires_after_secs':86400,'processing_info':self.statuses.pop(0)}
        elif 'command=STATUS' in url:data={'id':'99887766','processing_info':self.statuses.pop(0)}
        elif url.endswith('/tweets'):return {'data':{'id':'112233445566778899'}},{},201
        else:raise AssertionError('Unexpected endpoint')
        return {'data':data},{},200
    def run_upload(self,context_value=None,healthy=lambda:True):
        with patch.object(r,'json_http',side_effect=self.provider),patch.object(r.time,'sleep'):
            return r.publish_x(context_value or context(),self.portal,healthy,self.journal)
    def posts(self):return [v for url,v in self.calls if url.endswith('/tweets')]
    def test_chunk_upload_exact_caption_and_receipt(self):
        result=self.run_upload();self.assertEqual(result['receipt'],'https://x.com/i/web/status/112233445566778899')
        self.assertEqual(self.portal.preflights,2)
        chunks=[kw['body'] for url,kw in self.calls if url.endswith('/append')]
        self.assertEqual([c['segment_index'] for c in chunks],[0,1])
        self.assertEqual(b''.join(base64.b64decode(c['media']) for c in chunks),self.portal.video)
        self.assertEqual(self.posts()[0]['body'],{'text':'Exact reviewed caption','media':{'media_ids':['99887766']},'made_with_ai':True})
        self.assertEqual(self.journal.read('x-fixture')['phase'],'provider-accepted')
        self.assertTrue(all(url.startswith('https://api.x.com/') for url,_ in self.calls))
        self.assertTrue(all('OAI-Sites-Authorization' not in kw.get('headers',{}) for _,kw in self.calls))
        self.assertNotIn('fixture-access',json.dumps(self.journal.read('x-fixture')))
    def test_account_identity_checked_before_media_upload(self):
        self.reply['https://api.x.com/2/users/me']=({'data':{'id':'other-account'}},{},200)
        with self.assertRaises(r.RuntimeFailure):self.run_upload()
        self.assertEqual(len(self.calls),1);self.assertEqual(self.portal.preflights,0)
    def test_approval_and_numeric_identity_required(self):
        for changes in [{'approved':0},{'kind':'draft'}]:
            c=context();c['job'].update(changes)
            with self.assertRaises(r.RuntimeFailure):self.run_upload(c)
        c=context();c['account']['external_id']='@handle'
        with self.assertRaises(r.RuntimeFailure):self.run_upload(c)
        self.assertEqual(self.calls,[])
    def test_unapproved_platform_has_no_provider_path(self):
        c=context();c['account']['platform']='threads'
        with self.assertRaises(r.RuntimeFailure):r.publish(c,self.portal,lambda:True,self.journal)
        self.assertEqual(self.calls,[])
    def test_pause_after_processing_prevents_post(self):
        self.portal.revoke_on=2
        with self.assertRaises(r.RuntimeFailure) as e:self.run_upload()
        self.assertNotIsInstance(e.exception,r.UncertainUpload);self.assertEqual(self.posts(),[])
    def test_lost_lease_stops_before_upload(self):
        with self.assertRaises(r.RuntimeFailure):self.run_upload(healthy=lambda:False)
        self.assertEqual(len(self.calls),1);self.assertEqual(self.posts(),[])
    def test_media_processing_rejection_does_not_publish(self):
        self.statuses=[{'state':'failed','error':{'message':'private provider diagnostic'}}]
        with self.assertRaises(r.RuntimeFailure) as e:self.run_upload()
        self.assertNotIn('private provider diagnostic',str(e.exception));self.assertEqual(self.posts(),[])
    def test_unknown_or_missing_status_does_not_publish(self):
        self.reply['https://api.x.com/2/media/upload?command=STATUS&media_id=99887766']=({'data':{}},{},200)
        with self.assertRaises(r.RuntimeFailure):self.run_upload()
        self.assertEqual(self.posts(),[])
    def test_wait_limits_and_expired_media_stop(self):
        self.statuses=[{'state':'pending','check_after_secs':1000}]
        with self.assertRaises(r.RuntimeFailure):self.run_upload()
        self.assertEqual(self.posts(),[])
        self.reply['https://api.x.com/2/media/upload/initialize']=({'data':{'id':'99887766','expires_after_secs':0}},{},200)
        with self.assertRaises(r.RuntimeFailure):self.run_upload()
        self.assertEqual(self.posts(),[])
    def test_numeric_media_id_prevents_endpoint_injection(self):
        self.reply['https://api.x.com/2/media/upload/initialize']=({'data':{'id':'../other','expires_after_secs':86400}},{},200)
        with self.assertRaises(r.RuntimeFailure):self.run_upload()
        self.assertTrue(all('/../' not in url for url,_ in self.calls))
    def test_media_errors_on_success_status_stop_preparation(self):
        self.reply['https://api.x.com/2/media/upload/99887766/append']=({'data':{},'errors':[{'detail':'private-sentinel'}]},{},200)
        with self.assertRaises(r.RuntimeFailure) as e:self.run_upload()
        self.assertNotIn('private-sentinel',str(e.exception));self.assertEqual(self.posts(),[])
    def test_lost_post_response_is_uncertain_and_never_replayed(self):
        self.reply['https://api.x.com/2/tweets']=r.RuntimeFailure('timeout')
        with self.assertRaises(r.UncertainUpload):self.run_upload()
        self.assertEqual(len(self.posts()),1);self.assertEqual(self.journal.read('x-fixture')['phase'],'post-starting')
        with self.assertRaises(r.UncertainUpload):self.run_upload()
        self.assertEqual(len(self.posts()),1)
    def test_provider_rejection_distinguished_from_ambiguous_error(self):
        for status in (400,401,403,429,500,408):
            self.calls=[];self.statuses=[{'state':'succeeded'}];self.journal.write('x-fixture',{})
            self.reply['https://api.x.com/2/tweets']=r.ProviderHTTPFailure(status)
            with self.assertRaises(r.RuntimeFailure) as failure:self.run_upload()
            self.assertEqual(isinstance(failure.exception,r.UncertainUpload),status in (500,408))
            self.assertEqual(len(self.posts()),1)
    def test_valid_receipt_kept_even_with_provider_warnings(self):
        self.reply['https://api.x.com/2/tweets']=({'data':{'id':'123'},'errors':[{'detail':'warning'}]},{},201)
        self.assertEqual(self.run_upload()['receipt'],'https://x.com/i/web/status/123')
    def test_missing_success_receipt_is_uncertain(self):
        self.reply['https://api.x.com/2/tweets']=({'data':{}},{},201)
        with self.assertRaises(r.UncertainUpload):self.run_upload()
        self.assertEqual(len(self.posts()),1)
    def test_receipt_persistence_failure_never_reposts(self):
        real=self.journal.write
        def write(job,value):
            if value.get('phase')=='provider-accepted':raise r.RuntimeFailure('disk unavailable')
            real(job,value)
        with patch.object(self.journal,'write',side_effect=write):
            result=self.run_upload();self.assertEqual(result['receipt'],'https://x.com/i/web/status/112233445566778899')
        with self.assertRaises(r.UncertainUpload):self.run_upload()
        self.assertEqual(len(self.posts()),1)
    def test_all_persisted_receipt_phases_recover_without_provider_calls(self):
        for record in [{'phase':'provider-accepted','receipt':'https://x.com/i/web/status/123'},{'phase':'recorded','status':'succeeded','receipt':'https://x.com/i/web/status/123'},{'completion':{'status':'succeeded','receipt':'https://x.com/i/web/status/123'}}]:
            self.journal.write('x-fixture',record)
            self.assertEqual(self.run_upload()['receipt'],'https://x.com/i/web/status/123')
        self.assertEqual(self.calls,[])

    def test_malformed_success_journal_never_allows_resending(self):
        for record in [{'phase':'provider-accepted'},{'phase':'recorded','status':'succeeded','receipt':'https://x.com/owner/status/123'},{'completion':{'status':'succeeded','receipt':'invalid'}},{'phase':'post-confirmation-needed','receipt':'invalid'}]:
            self.journal.write('x-fixture',record)
            with self.assertRaises(r.UncertainUpload):self.run_upload()
        self.assertEqual(self.calls,[])
    def test_lease_rechecked_after_final_preflight(self):
        valid=[True]
        real=self.portal.call
        def final_pause(*a,**kw):
            result=real(*a,**kw)
            if self.portal.preflights==2:valid[0]=False
            return result
        with patch.object(self.portal,'call',side_effect=final_pause):
            with self.assertRaises(r.RuntimeFailure):self.run_upload(healthy=lambda:valid[0])
        self.assertEqual(self.posts(),[])
    def test_unexpected_success_status_keeps_receipt_for_review(self):
        self.reply['https://api.x.com/2/tweets']=({'data':{'id':'123'}},{},200)
        result=self.run_upload();self.assertEqual(result['status'],'uncertain');self.assertEqual(result['receipt'],'https://x.com/i/web/status/123')
        self.assertEqual(self.run_upload()['status'],'uncertain');self.assertEqual(len(self.posts()),1)

    def test_media_expiry_rechecked_after_final_preflight(self):
        current=[1000000];real=self.portal.call
        def expire(*a,**kw):
            result=real(*a,**kw)
            if self.portal.preflights==2:current[0]+=90000
            return result
        with patch.object(r.time,'time',side_effect=lambda:current[0]),patch.object(self.portal,'call',side_effect=expire):
            with self.assertRaises(r.RuntimeFailure):self.run_upload()
        self.assertEqual(self.posts(),[])
    def test_refreshed_identity_checked_before_posting(self):
        base=self.provider;lookups=[0]
        def provider(url,**kw):
            result=base(url,**kw)
            if url.endswith('/users/me'):
                lookups[0]+=1
                if lookups[0]==2:return {'data':{'id':'different-account'}},{},200
            return result
        with patch.object(r.XCredentialStore,'token',side_effect=['first-token','second-token']),patch.object(r,'json_http',side_effect=provider),patch.object(r.time,'sleep'):
            with self.assertRaises(r.RuntimeFailure):r.publish_x(context(),self.portal,lambda:True,self.journal)
        self.assertEqual(lookups[0],2);self.assertEqual(self.posts(),[])
    def test_uncertain_candidate_receipt_survives_recovery(self):
        for record in [{'completion':{'status':'uncertain','receipt':'https://x.com/i/web/status/123'}},{'phase':'recorded','status':'uncertain','receipt':'https://x.com/i/web/status/123'}]:
            self.journal.write('x-fixture',record)
            result=self.run_upload();self.assertEqual(result['status'],'uncertain');self.assertEqual(result['receipt'],'https://x.com/i/web/status/123')
        self.assertEqual(self.calls,[])
    def test_worker_preserves_known_receipt_after_intermediate_disk_error(self):
        real_write=self.journal.write;preflight=self.portal.call;completed=[]
        def write(job,value):
            if value.get('phase')=='provider-accepted':raise r.RuntimeFailure('intermediate disk error')
            real_write(job,value)
        def portal_call(action,**body):
            if action=='complete':completed.append(body);return {'ok':True}
            return preflight(action,**body)
        with patch.object(self.journal,'write',side_effect=write),patch.object(self.portal,'call',side_effect=portal_call),patch.object(r,'json_http',side_effect=self.provider),patch.object(r.time,'sleep'),patch('builtins.print'):
            r.Worker(self.portal,self.journal).process(context())
        self.assertEqual(completed[0]['receipt'],'https://x.com/i/web/status/112233445566778899')
        self.assertEqual(self.journal.read('x-fixture')['receipt'],completed[0]['receipt'])
        self.assertEqual(len(self.posts()),1)

class XCredentialTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.store=r.XCredentialStore(self.directory.name)
        self.env=patch.dict(os.environ,{'X_FIXTURE':json.dumps(CONFIG)},clear=True);self.env.start()
        self.answer=({'access_token':'fixture-access','expires_in':7200,'refresh_token':'rotated-refresh','token_type':'bearer'},{},200)
    def tearDown(self):self.env.stop();self.directory.cleanup()
    def state(self):return json.loads((Path(self.directory.name)/'X_FIXTURE.json').read_text())
    def expire(self):
        value=self.state();value['expires_at']=0;r.atomic_json(Path(self.directory.name)/'X_FIXTURE.json',value)
    def test_rotation_persisted_private_before_reuse(self):
        with patch.object(r,'json_http',return_value=self.answer) as request:
            self.assertEqual(self.store.token(ACCOUNT),'fixture-access')
            self.assertEqual(self.store.token(ACCOUNT),'fixture-access');self.assertEqual(request.call_count,1)
            self.assertEqual(request.call_args.args[0],'https://api.x.com/2/oauth2/token')
            self.assertEqual(base64.b64decode(request.call_args.kwargs['headers']['Authorization'].split()[1]).decode(),'fixture-client:fixture-secret')
        self.assertEqual(self.state()['refresh_token'],'rotated-refresh')
        self.assertEqual((Path(self.directory.name)/'X_FIXTURE.json').stat().st_mode&0o777,0o600)
        self.expire()
        with patch.object(r,'json_http',return_value=self.answer) as request:
            self.store.token(ACCOUNT)
            self.assertEqual(urllib.parse.parse_qs(request.call_args.kwargs['body'].decode())['refresh_token'],['rotated-refresh'])
    def test_public_client_sends_client_id_without_basic_secret(self):
        os.environ['X_FIXTURE']=json.dumps({k:v for k,v in CONFIG.items() if k!='client_secret'})
        with patch.object(r,'json_http',return_value=self.answer) as request:
            self.store.token(ACCOUNT)
            self.assertNotIn('Authorization',request.call_args.kwargs['headers'])
            self.assertEqual(urllib.parse.parse_qs(request.call_args.kwargs['body'].decode())['client_id'],['fixture-client'])
    def test_ambiguous_refresh_quarantines_until_new_consent(self):
        with patch.object(r,'json_http',side_effect=r.RuntimeFailure('timeout')) as request:
            with self.assertRaises(r.RuntimeFailure):self.store.token(ACCOUNT)
            with self.assertRaises(r.RuntimeFailure):self.store.token(ACCOUNT)
            self.assertEqual(request.call_count,1)
        self.assertEqual(self.state()['phase'],'refresh-starting')
        os.environ['X_FIXTURE']=json.dumps(dict(CONFIG,refresh_token='new-consent-token'))
        with patch.object(r,'json_http',return_value=self.answer):self.assertEqual(self.store.token(ACCOUNT),'fixture-access')
    def test_concurrent_refreshes_use_one_rotating_token_request(self):
        with patch.object(r,'json_http',return_value=self.answer) as request,concurrent.futures.ThreadPoolExecutor(8) as pool:
            values=list(pool.map(lambda _:self.store.token(ACCOUNT),range(8)))
            self.assertEqual(values,['fixture-access']*8);self.assertEqual(request.call_count,1)
    def test_failed_state_write_blocks_refresh_request(self):
        with patch.object(r,'atomic_json',side_effect=r.RuntimeFailure('disk unavailable')),patch.object(r,'json_http') as request:
            with self.assertRaises(r.RuntimeFailure):self.store.token(ACCOUNT)
            request.assert_not_called()
    def test_invalid_token_response_is_redacted_and_quarantined(self):
        with patch.object(r,'json_http',return_value=({'access_token':'private-sentinel\r\nInjected','expires_in':7200},{},200)) as request:
            with self.assertRaises(r.RuntimeFailure) as failure:self.store.token(ACCOUNT)
            self.assertNotIn('private-sentinel',str(failure.exception))
            with self.assertRaises(r.RuntimeFailure):self.store.token(ACCOUNT)
            self.assertEqual(request.call_count,1)
    def test_bad_refs_and_missing_credentials_fail_before_network(self):
        with patch.object(r,'json_http') as request:
            for ref in ['../private','OPENAI_API_KEY','MISSING_CREDENTIAL']:
                with self.assertRaises(r.RuntimeFailure):self.store.token(dict(ACCOUNT,credential_ref=ref))
            request.assert_not_called()
    def test_credential_files_never_appear_in_task_completion_recovery(self):
        journal=r.Journal(self.directory.name);store=r.XCredentialStore(journal.path/'credentials')
        with patch.object(r,'json_http',return_value=self.answer):store.token(ACCOUNT)
        self.assertEqual(list(journal.pending()),[])

if __name__=='__main__':unittest.main()
