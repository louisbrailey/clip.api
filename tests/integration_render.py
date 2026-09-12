"""Loopback-only render integration, including one real FFmpeg worker job. No providers."""
import concurrent.futures
import hashlib
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from unittest.mock import patch

ROOT=Path(__file__).parents[1];BASE='http://localhost:5173'
loader=importlib.util.spec_from_file_location('render_http_runtime',ROOT/'worker/runtime.py');r=importlib.util.module_from_spec(loader);loader.loader.exec_module(r)
jar=http.cookiejar.CookieJar();urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)).open(BASE+'/signin-with-chatgpt?return_to=/').read()
COOKIE='; '.join(c.name+'='+c.value for c in jar);checks=0
def check(ok,label):
    global checks
    assert ok,label;checks+=1;print('PASS',label)
def req(body=None,key=None,path='/api/control',raw=None,extra=None):
    headers={'Origin':BASE,'Content-Type':'application/json',**({'Authorization':'Bearer '+key} if key else {'Cookie':COOKIE}),**(extra or {})}
    request=urllib.request.Request(BASE+path,headers=headers,data=raw if raw is not None else json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(request,timeout=90) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as e:
        try:return e.code,json.load(e)
        except ValueError:return e.code,{}
def action(action_name,**kw):return req(dict(action=action_name,**kw))
def queue(**kw):
    body=dict(request_id=str(uuid.uuid4()),title='Original ocean noise fixture',seconds=10,noise='pink',theme='ocean',scheduled=int(time.time()*1000),approved=True);body.update(kw)
    code,result=action('ambient-render',**body);return code,result,body
def job(jid):return next(j for j in req(path='/api/control?q='+jid)[1]['jobs'] if j['id']==jid)

try:
    check(queue(approved=False)[0]==400,'render requires explicit original-recipe approval')
    check(queue(seconds=301)[0]==400,'oversized render duration rejected')
    check(queue(noise='pink; curl example.com')[0]==400,'arbitrary renderer input rejected')
    code,created,body=queue();jid=created['id'];check(code==200,'approved ambient render queued')
    spec=job(jid)['render_spec']
    check(action('ambient-render',**body)[0]==200 and job(jid)['render_spec']==spec,'creation replay retains one job and immutable seed')
    check(action('ambient-render',**dict(body,noise='brown'))[0]==409,'creation replay rejects changed recipe')
    check(action('ambient-render',**dict(body,scheduled=body['scheduled']+1))[0]==409,'creation replay rejects changed start time')
    _,key_data=action('worker-key');key=key_data['token']
    check(req(dict(action='ambient-render',**body),key=key)[0]==403,'worker cannot approve a render recipe')
    code,c=req(dict(action='claim',request_id=str(uuid.uuid4())),key=key);j=c['job']
    check(code==200 and j['id']==jid and j['reserve']==0,'render task is leased with no model-token reservation')
    pre=dict(action='render-preflight',id=jid,lease=j['lease'])
    check(req(pre)[0]==403,'browser cannot use render worker preflight')
    check(req(raw=b'',path='/api/render')[0]==403,'browser cannot impersonate generated-media upload')
    check(req(pre,key=key)[0]==200,'scoped worker can preflight its render')
    check(req(dict(pre,lease=str(uuid.uuid4())),key=key)[0]==409,'wrong render lease rejected')
    success=dict(action='complete',id=jid,lease=j['lease'],status='succeeded',tokens=0,receipt='asset:'+str(uuid.uuid4()))
    check(req(success,key=key)[0]==400,'render cannot succeed without a committed library asset')
    state=req()[1];ambient=next(a for a in state['agents'] if a['id']=='ambient')
    action('agent',**dict(ambient,paused=True));check(req(pre,key=key)[0]==409,'ancestor pause stops render preflight')
    check(req(raw=b'',path='/api/render',key=key,extra={'X-Render-Job':jid,'X-Render-Lease':j['lease']})[0]==409,'ancestor pause also stops media registration')
    ambient=next(a for a in req()[1]['agents'] if a['id']=='ambient');action('agent',**dict(ambient,paused=False))
    media=(ROOT/'outputs/ambient-pink-noise.mp4').read_bytes();digest=hashlib.sha256(media).hexdigest()
    with patch.dict(os.environ,{'PATH':os.environ.get('PATH',''),'FFMPEG_BIN':os.environ['FFMPEG_BIN']},clear=True):
        portal=r.Portal(BASE,key)
        try:portal.render_output(jid,j['lease'],media,'0'*64);rejected=False
        except r.RuntimeFailure:rejected=True
        check(rejected,'mismatched media digest cannot be registered')
        with concurrent.futures.ThreadPoolExecutor(2) as pool:saved=list(pool.map(lambda _:portal.render_output(jid,j['lease'],media,digest),range(2)))
        check(saved[0]['asset']==saved[1]['asset'],'concurrent uploads select one immutable canonical asset')
        aid=saved[0]['asset'];check(job(jid)['asset']==aid,'canonical generated asset is linked to its render job')
        check(portal.render_output(jid,j['lease'],media,digest)['asset']==aid,'lost-response upload retry recovers the same asset')
        check(req(dict(success,tokens=1,receipt='asset:'+aid),key=key)[0]==400,'render completion cannot claim model-token usage')
        with patch.object(r,'render_process',side_effect=AssertionError('Saved output must not rerender')):
            with tempfile.TemporaryDirectory() as journal:r.Worker(portal,r.Journal(journal)).process(c)
        check(job(jid)['status']=='succeeded','worker recovers saved output and completes without rerendering')
        code,created,_=queue(title='Actual queued original ocean video');actual=created['id']
        code,c=req(dict(action='claim',request_id=str(uuid.uuid4())),key=key);assert c['job']['id']==actual
        with tempfile.TemporaryDirectory() as journal:r.Worker(portal,r.Journal(journal)).process(c)
        finished=job(actual);check(finished['status']=='succeeded' and bool(finished['asset']),'real worker render saves video and completes through the local portal')
        aid=finished['asset'];video=portal.media(aid)
        asset=next(a for a in req()[1]['assets'] if a['id']==aid)
        check(hashlib.sha256(video).hexdigest()==asset['sha256'],'downloaded video matches persisted provenance digest')
        check(asset['source_job']==actual and asset['rights']=='original' and asset['expires'] is None,'generated asset records its originating job and original rights')
        output=ROOT/'outputs/ambient-queued-ocean.mp4';output.write_bytes(video)
        subprocess.run([os.environ['FFMPEG_BIN'],'-hide_banner','-loglevel','error','-i',str(output),'-f','null','-'],check=True,timeout=60,capture_output=True)
        check(True,'real generated video fully decodes with FFmpeg')
        output.with_suffix('.rights.json').write_text(json.dumps({k:asset[k] for k in ('id','name','source_job','sha256','rights','evidence','expires')},indent=2)+'\n')
        check(not any(x['kind']=='publish' and x['asset']==aid for x in req()[1]['jobs']),'render completion does not approve or enqueue publication')
finally:action('revoke-key')
print(f'{checks} ambient render HTTP checks passed, including actual FFmpeg rendering and full video decode. No model/social API requests.')
