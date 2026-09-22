"""Threads provider fixtures; no requests leave the test process."""
import importlib.util, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('threads_runtime',Path(__file__).parents[1]/'worker/runtime.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
ACCOUNT={'platform':'threads','external_id':'17841412345678901','credential_ref':'THREADS_FIXTURE','authorized':1};URL='https://staging.example.com/original-video.mp4?signature=abc123'
def context():return {'job':{'id':'threads-fixture','lease':'threads-lease','mode':'live','kind':'publish','approved':1,'asset':'media','brief':'Exact Threads text','media_url':URL},'account':dict(ACCOUNT)}
class Portal:
    def __init__(self):self.preflights=0;self.revoke_on=0
    def media(self,asset):return b'0000ftyp-fixture'
    def call(self,action,**kw):
        assert action=='preflight' and kw=={'id':'threads-fixture','lease':'threads-lease'};self.preflights+=1
        if self.preflights==self.revoke_on:raise r.RuntimeFailure('Publication paused')
        return {'ok':True}

class ThreadsPublishTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup);self.journal=r.Journal(self.directory.name);self.portal=Portal();self.calls=[]
    def provider(self,url,**kw):
        self.calls.append((url,kw))
        if url=='https://graph.threads.net/v1.0/me?fields=id,username':return {'id':ACCOUNT['external_id'],'username':'fixture'},{},200
        if url.endswith('/content_publishing_limit_threads'):return {'config':{'quota_total':5},'quota_usage':1},{},200
        if url.endswith('/threads'):return {'id':'123456789012345678'},{},200
        if url.endswith('/123456789012345678?fields=status,error_message'):return {'status':'FINISHED'},{},200
        if url.endswith('/threads_publish'):return {'id':'445566778899'},{},200
        raise AssertionError(url)
    def run_publish(self,c=None):
        with patch.dict('os.environ',{'THREADS_FIXTURE':'{"access_token":"private-token"}'}),patch.object(r,'json_http',side_effect=self.provider),patch.object(r.time,'sleep'):
            return r.publish_threads(c or context(),self.portal,lambda:True,self.journal)
    def test_exact_text_staging_url_quota_status_and_receipt(self):
        result=self.run_publish();self.assertEqual(result['receipt'],'threads-media:445566778899')
        create=next(k for u,k in self.calls if u.endswith('/threads'))
        self.assertEqual(create['body'],{'media_type':'VIDEO','video_url':URL,'text':'Exact Threads text'});self.assertEqual(self.portal.preflights,3)
        self.assertTrue(all('OAI-Sites-Authorization' not in k.get('headers',{}) for _,k in self.calls))
    def test_wrong_identity_url_or_oversized_text_never_publishes(self):
        for changes in ({'external_id':'other'},{'media_url':'http://localhost/private.mp4'},{'brief':'x'*501}):
            c=context()
            if 'external_id' in changes:c['account']['external_id']=changes['external_id']
            else:c['job'].update(changes)
            with self.assertRaises(r.RuntimeFailure):self.run_publish(c)
        self.assertFalse(any(u.endswith('/threads_publish') for u,_ in self.calls))
    def test_rejected_container_and_pause_do_not_publish(self):
        self.portal.revoke_on=3
        with self.assertRaises(r.RuntimeFailure):self.run_publish()
        self.assertFalse(any(u.endswith('/threads_publish') for u,_ in self.calls))
    def test_lost_publish_is_uncertain_and_never_replayed(self):
        original=self.provider
        def provider(url,**kw):
            self.calls=[]
            self.calls.append((url,kw))
            if url.endswith('/threads_publish'):raise r.RuntimeFailure('timeout')
            return original(url,**kw)
        with patch.object(r,'json_http',side_effect=provider):
            with patch.dict('os.environ',{'THREADS_FIXTURE':'{"access_token":"private-token"}'}),patch.object(r.time,'sleep'):
                with self.assertRaises(r.UncertainUpload):r.publish_threads(context(),self.portal,lambda:True,self.journal)
                with self.assertRaises(r.UncertainUpload):r.publish_threads(context(),self.portal,lambda:True,self.journal)
        self.assertEqual(len([u for u,_ in self.calls if u.endswith('/threads_publish')]),1)
    def test_saved_receipt_recovers_without_provider_calls(self):
        self.journal.write('threads-fixture',{'phase':'provider-accepted','receipt':'threads-media:123'})
        with patch.object(r,'json_http') as send:self.assertEqual(self.run_publish()['status'],'succeeded')
        send.assert_not_called()
if __name__=='__main__':unittest.main()
