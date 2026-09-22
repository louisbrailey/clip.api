"""Instagram provider fixtures; no requests leave the test process."""
import importlib.util, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('instagram_runtime',Path(__file__).parents[1]/'worker/runtime.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
ACCOUNT={'platform':'instagram','external_id':'17841412345678901','credential_ref':'INSTAGRAM_FIXTURE','authorized':1}
def context():return {'job':{'id':'ig-fixture','lease':'ig-lease','mode':'live','kind':'publish','approved':1,'asset':'media','brief':'Exact Instagram caption'},'account':dict(ACCOUNT)}
class Portal:
    def __init__(self):self.preflights=0;self.revoke_on=0;self.video=b'0000ftyp'+b'fixture-video'*100
    def media(self,asset):return self.video
    def call(self,action,**kw):
        assert action=='preflight' and kw=={'id':'ig-fixture','lease':'ig-lease'};self.preflights+=1
        if self.preflights==self.revoke_on:raise r.RuntimeFailure('Publication paused')
        return {'ok':True}
class InstagramTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.journal=r.Journal(self.directory.name);self.portal=Portal();self.calls=[]
    def provider(self,url,**kw):
        self.calls.append((url,kw))
        if url=='https://graph.facebook.com/v24.0/me?fields=id':return {'id':ACCOUNT['external_id']},{},200
        if url=='https://graph.facebook.com/v24.0/'+ACCOUNT['external_id']+'/content_publishing_limit':return {'config':{'quota_total':50},'quota_usage':1},{},200
        if url.startswith('https://rupload.facebook.com/ig-api-upload/'):
            phase=kw['body'].get('upload_phase')
            if phase=='start':return {'upload_id':'99887766'},{},200
            if phase=='transfer':return {'upload_id':'99887766','success':True},{},200
            if phase=='finish':return {'upload_id':'99887766','success':True},{},200
        if url.endswith('/media'):return {'id':'12345678901'},{},200
        if url.endswith('/media_publish'):return {'id':'99887766554433'},{},200
        raise AssertionError(url)
    def run_publish(self,c=None):
        with patch.dict('os.environ',INSTAGRAM_FIXTURE='{"access_token":"private-token"}'),patch.object(r,'json_http',side_effect=self.provider):
            return r.publish_instagram(c or context(),self.portal,lambda:True,self.journal)
    def test_upload_container_publish_exact_caption_and_receipt(self):
        result=self.run_publish()
        self.assertEqual(result,{'status':'succeeded','result':'Instagram reel uploaded through the approved professional account. Check Instagram Studio for final visibility and review state.','receipt':'instagram-media:99887766554433','tokens':0})
        self.assertEqual(self.portal.preflights,4)
        create=next(k for u,k in self.calls if u.endswith('/media'))
        self.assertEqual(create['body'],{'caption':'Exact Instagram caption','media_type':'REELS','share_to_feed':True,'upload_id':'99887766'})
        transfer=next(k for u,k in self.calls if isinstance(k.get('body'),dict) and k['body'].get('upload_phase')=='transfer')
        self.assertEqual(transfer['body']['x-entity-length'],len(self.portal.video))
        self.assertTrue(all('OAI-Sites-Authorization' not in k.get('headers',{}) for _,k in self.calls))
    def test_wrong_identity_and_caption_never_publish(self):
        c=context();c['account']['external_id']='other'
        with self.assertRaises(r.RuntimeFailure):self.run_publish(c)
        c=context();c['job']['brief']='x'*2201
        with self.assertRaises(r.RuntimeFailure):self.run_publish(c)
        self.assertFalse(any(u.endswith('/media_publish') for u,_ in self.calls))
    def test_pause_blocks_public_side_effect(self):
        self.portal.revoke_on=3
        with self.assertRaises(r.RuntimeFailure):self.run_publish()
        self.assertFalse(any(u.endswith('/media_publish') for u,_ in self.calls))
    def test_lost_publish_is_uncertain_and_never_replayed(self):
        original=self.provider
        def provider(url,**kw):
            self.calls=[]
            self.calls.append((url,kw))
            if url.endswith('/media_publish'):raise r.RuntimeFailure('timeout')
            return original(url,**kw)
        with patch.object(r,'json_http',side_effect=provider):
            with patch.dict('os.environ',INSTAGRAM_FIXTURE='{"access_token":"private-token"}'):
                with self.assertRaises(r.UncertainUpload):r.publish_instagram(context(),self.portal,lambda:True,self.journal)
                with self.assertRaises(r.UncertainUpload):r.publish_instagram(context(),self.portal,lambda:True,self.journal)
        self.assertEqual(len([u for u,_ in self.calls if u.endswith('/media_publish')]),1)
    def test_saved_receipt_recovers_without_provider_calls(self):
        self.journal.write('ig-fixture',{'phase':'provider-accepted','receipt':'instagram-media:123'})
        with patch.object(r,'json_http') as send:self.assertEqual(self.run_publish()['status'],'succeeded')
        send.assert_not_called()
if __name__=='__main__':unittest.main()
