import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('runtime',Path(__file__).parents[1]/'worker/runtime.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def context(kind='plan'):
    return {'job':{'id':'test-job','kind':kind,'mode':'live','title':'Original meditation','brief':'Create an original breathing script for our audience.','lane':'ambient','asset':'d215cdf8-426e-48c9-a032-fa4c84f1c3c8','lease':'lease'},'agent':{'id':'astra','model':'gpt-6-astra','instructions':'Use a writer and editor.'},'dependency':''}

class WorkerTests(unittest.TestCase):
    def test_exact_astra_model(self):
        p=r.model_payload(context());self.assertEqual(p['model'],'gpt-6-astra');self.assertEqual(p['max_output_tokens'],3000);self.assertNotIn('tools',p);self.assertFalse(p['store'])
    def test_head_model_cannot_be_substituted(self):
        c=context();c['agent']['model']='other-model'
        with self.assertRaises(r.RuntimeFailure):r.model_payload(c)
    def test_utf8_input_budget_is_bounded(self):
        c=context();c['job']['brief']='😀'*6000
        with self.assertRaises(r.RuntimeFailure):r.model_payload(c)
    def test_unsupported_task_cannot_execute(self):
        with self.assertRaises(r.RuntimeFailure):r.model_payload(context('shell'))
    def test_plan_fanout_is_bounded(self):
        with self.assertRaises(r.RuntimeFailure):r.validate_plan({'tasks':[{'title':'Do task','brief':'Create original text','role':'writer'}]*9})
    def test_plan_cannot_include_commands_or_credentials(self):
        with self.assertRaises(r.RuntimeFailure):r.validate_plan({'tasks':[{'title':'Do task','brief':'Create original text','role':'writer','command':'rm -rf /'}]})
    def test_plan_role_allowlist(self):
        with self.assertRaises(r.RuntimeFailure):r.validate_plan({'tasks':[{'title':'Engage','brief':'Write many automated replies','role':'reply-bot'}]})
    def test_valid_plan(self):
        self.assertEqual(len(r.validate_plan({'tasks':[{'title':'Write script','brief':'Create an original script','role':'writer'}]})),1)
    def test_nonlocal_plain_http_rejected(self):
        with self.assertRaises(r.RuntimeFailure):r.Portal('http://example.com','cs_'+'1'*64)
    def test_credentials_in_url_rejected(self):
        with self.assertRaises(r.RuntimeFailure):r.Portal('https://key@example.com','cs_'+'1'*64)
    def test_local_endpoint_allowed(self):
        self.assertEqual(r.Portal('http://localhost:5173','cs_'+'1'*64).url,'http://localhost:5173')
    def test_bad_worker_key_rejected(self):
        with self.assertRaises(r.RuntimeFailure):r.Portal('https://example.com','password')
    def test_missing_openai_key_fails_closed(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(r.RuntimeFailure):r.run_model(context())
    def test_responses_output_parsing(self):
        output=json.dumps({'tasks':[{'title':'Write script','brief':'Create an original script','role':'writer'}]})
        response={'status':'completed','output':[{'type':'reasoning'},{'type':'message','content':[{'type':'output_text','text':output}]}],'usage':{'total_tokens':400}}
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.object(r,'json_http',return_value=(response,{},200)):
            result=r.run_model(context());self.assertEqual(result['tokens'],400);self.assertEqual(result['plan'][0]['role'],'writer')
    def test_incomplete_model_output_rejected(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.object(r,'json_http',return_value=({'status':'incomplete'},{},200)):
            with self.assertRaises(r.RuntimeFailure):r.run_model(context())
    def test_receipt_journal_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            j=r.Journal(d);j.write('abc',{'completion':{'id':'abc','receipt':'video'}})
            self.assertEqual(list(j.pending())[0][1]['receipt'],'video');self.assertEqual((Path(d)/'abc.json').stat().st_mode&0o777,0o600)
            j.write('abc',{'phase':'recorded'});self.assertEqual(list(j.pending()),[])
    def test_journal_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(r.RuntimeFailure):r.Journal(d).write('../secrets',{})
    def test_youtube_identity_mismatch_stops_upload(self):
        c=context('publish');c['account']={'platform':'youtube','external_id':'wrong'}
        with tempfile.TemporaryDirectory() as d,patch.object(r,'youtube_token',return_value='test'),patch.object(r,'json_http',return_value=({'items':[{'id':'actual'}]},{},200)):
            with self.assertRaises(r.RuntimeFailure):r.publish_youtube(c,None,lambda:True,r.Journal(d))
    def test_private_youtube_upload_and_receipt(self):
        c=context('publish');c['account']={'platform':'youtube','external_id':'channel'}
        class Portal:
            def call(self,*a,**kw):return {'ok':True}
            def media(self,*a):return b'0000ftyp00000000'
        replies=[({'items':[{'id':'channel'}]},{},200),({'id':'abcdefghi01'},{},200)]
        with tempfile.TemporaryDirectory() as d,patch.object(r,'youtube_token',return_value='test'),patch.object(r,'json_http',side_effect=replies) as mock,patch.object(r,'http',return_value=(b'',{'Location':'https://www.googleapis.com/upload/session/test'},200)) as init:
            result=r.publish_youtube(c,Portal(),lambda:True,r.Journal(d));self.assertIn('abcdefghi01',result['receipt'])
            self.assertEqual(init.call_args.kwargs['body']['status']['privacyStatus'],'private')
    def test_ambiguous_upload_is_never_automatically_retried(self):
        c=context('publish');c['account']={'platform':'youtube','external_id':'channel'}
        class Portal:
            def call(self,*a,**kw):return {'ok':True}
            def media(self,*a):return b'0000ftyp00000000'
        replies=[({'items':[{'id':'channel'}]},{},200),r.RuntimeFailure('timeout')]
        with tempfile.TemporaryDirectory() as d,patch.object(r,'youtube_token',return_value='test'),patch.object(r,'json_http',side_effect=replies) as mock,patch.object(r,'http',return_value=(b'',{'Location':'https://www.googleapis.com/upload/session/test'},200)) as init:
            with self.assertRaises(r.UncertainUpload):r.publish_youtube(c,Portal(),lambda:True,r.Journal(d))
            self.assertEqual(mock.call_count,2)
if __name__=='__main__':unittest.main()
