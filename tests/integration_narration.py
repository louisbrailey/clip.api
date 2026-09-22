"""Loopback proof for scheduled, operator-approved original narration."""
import hashlib,http.cookiejar,importlib.util,json,os,subprocess,tempfile,time,urllib.error,urllib.request,uuid
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).parents[1]; BASE='http://localhost:5173'; FFMPEG=os.environ['FFMPEG_BIN']; NARRATOR=os.environ.get('NARRATOR_BIN','/usr/bin/say')
loader=importlib.util.spec_from_file_location('narration_runtime',ROOT/'worker/runtime.py'); r=importlib.util.module_from_spec(loader); loader.loader.exec_module(r)
jar=http.cookiejar.CookieJar(); urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)).open(BASE+'/signin-with-chatgpt?return_to=/').read(); COOKIE='; '.join(c.name+'='+c.value for c in jar); checks=0
def check(ok,label):
 global checks
 assert ok,label; checks+=1; print('PASS',label)
def req(body=None,key=None,path='/api/control'):
 headers={'Origin':BASE,'Content-Type':'application/json',**({'Authorization':'Bearer '+key} if key else {'Cookie':COOKIE})}; request=urllib.request.Request(BASE+path,headers=headers,data=json.dumps(body).encode() if body is not None else None)
 try:
  with urllib.request.urlopen(request,timeout=90) as response:return response.status,json.load(response)
 except urllib.error.HTTPError as error:return error.code,json.load(error)
def action(action_name,**kw): return req(dict(action=action_name,**kw))
sid=None
try:
 script='Breathe in slowly. Breathe out gently. This original narration belongs to the operator for this recurring meditation.'
 code,account=action('account',platform='youtube',handle='@narrated-'+uuid.uuid4().hex[:12],lane='ambient',external_id='channel-'+uuid.uuid4().hex,credential_ref='TEST_NARRATION',authorized=True,daily_limit=1); check(code==200,'ambient account fixture saved')
 payload=dict(request_id=str(uuid.uuid4()),account=account['id'],title='Recurring narrated meditation',brief='Create original meditations and leave publication for separate review.',mode='live',production_kind='ambient',render_recipe=dict(seconds=10,noise='pink',theme='night',script=script),render_approved=True,interval_minutes=60,next_run=int(time.time()*1000)-7200000,max_runs=1,paused=False)
 bad=dict(payload,request_id=str(uuid.uuid4()),render_recipe=dict(payload['render_recipe'],script='x'*3001)); check(action('schedule',**bad)[0]==400,'oversized narration script rejected before scheduling')
 code,saved=action('schedule',**payload); check(code==200,'approved recurring narrated video schedule saved'); sid=saved['id']; check(action('schedule',**payload)[1]['id']==sid,'narrated schedule creation replay is stable')
 _,keys=action('worker-key'); key=keys['token']; action('account-pause',id=account['id'],paused=True); check(req(dict(action='claim',request_id=str(uuid.uuid4())),key=key)[1]['job'] is None,'paused account holds before narration synthesis'); action('account-pause',id=account['id'],paused=False)
 code,context=req(dict(action='claim',request_id=str(uuid.uuid4())),key=key); j=context['job']; check(code==200 and j and j['kind']=='render','narrated schedule expanded into approved render'); spec=json.loads(j['render_spec']); check(spec['script']==script,'portal saved exact recurring narration script')
 editor=next(a for a in req()[1]['agents'] if a['id']=='ambient-editor'); action('agent',**dict(editor,paused=True)); check(req(dict(action='render-preflight',id=j['id'],lease=j['lease']),key=key)[0]==409,'editor pause fences narration preflight'); editor=next(a for a in req()[1]['agents'] if a['id']=='ambient-editor'); action('agent',**dict(editor,paused=False)); check(req(dict(action='render-preflight',id=j['id'],lease=str(uuid.uuid4())),key=key)[0]==409,'stale narration render lease rejected')
 with tempfile.TemporaryDirectory() as journal:
  with patch.dict(os.environ,{'PATH':os.environ.get('PATH',''),'FFMPEG_BIN':FFMPEG,'NARRATOR_BIN':NARRATOR},clear=True): r.Worker(r.Portal(BASE,key),r.Journal(journal)).process(context)
 finished=next(x for x in req(path='/api/control?q='+j['id'])[1]['jobs'] if x['id']==j['id']); check(finished['status']=='succeeded' and bool(finished['asset']),'fresh worker completed narrated video'); asset=next(a for a in req()[1]['assets'] if a['id']==finished['asset']); video=r.Portal(BASE,key).media(asset['id']); output=ROOT/'outputs/ambient-recurring-narrated.mp4'; output.write_bytes(video); check(hashlib.sha256(video).hexdigest()==asset['sha256'],'downloaded narrated video matches digest')
 evidence='Original procedural ambient color video, synthesized noise and the operator-approved original narration script. Generated locally; no third-party footage, soundtrack or voice recording.'; check(asset['evidence']==evidence and asset['rights']=='original','narrated original rights evidence persisted'); subprocess.run([FFMPEG,'-hide_banner','-loglevel','error','-i',str(output),'-map','0:a','-f','null','-'],check=True,timeout=60,capture_output=True); check(True,'narrated audio track fully decodes'); output.with_suffix('.rights.json').write_text(json.dumps({k:asset[k] for k in ('id','name','source_job','sha256','rights','evidence','expires')},indent=2)+'\n')
finally:
 if sid:
  row=next(x for x in req()[1]['schedules'] if x['id']==sid); action('schedule-pause',id=sid,revision=row['revision'],paused=True)
 action('revoke-key')
print(f'{checks} narration integration checks passed. No model/social API requests were made.')
