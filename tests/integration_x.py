"""Loopback-only X approval and queue checks. No X/model API requests are made."""
import concurrent.futures
import http.cookiejar
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid

BASE='http://localhost:5173'
jar=http.cookiejar.CookieJar();urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)).open(BASE+'/signin-with-chatgpt?return_to=/').read()
COOKIE='; '.join(c.name+'='+c.value for c in jar)
checks=0
def check(ok,label):
    global checks
    assert ok,label;checks+=1;print('PASS',label)
def req(body=None,token=None,path='/api/control'):
    headers={'Origin':BASE,'Content-Type':'application/json'}
    headers.update({'Authorization':'Bearer '+token} if token else {'Cookie':COOKIE})
    request=urllib.request.Request(BASE+path,headers=headers,data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(request,timeout=30) as result:return result.status,json.load(result)
    except urllib.error.HTTPError as e:
        try:value=json.load(e)
        except ValueError:value={}
        return e.code,value
def action(name,**kw):return req(dict(action=name,**kw))
def upload():
    boundary='x-fixture-'+uuid.uuid4().hex
    fields={'rights':'original','evidence':'Original procedural ambient video created by the bundled renderer for a local test.'}
    parts=[f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode() for name,value in fields.items()]
    parts += [f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="x-fixture.mp4"\r\nContent-Type: video/mp4\r\n\r\n'.encode(),Path('outputs/ambient-pink-noise.mp4').read_bytes(),f'\r\n--{boundary}--\r\n'.encode()]
    request=urllib.request.Request(BASE+'/api/assets',data=b''.join(parts),headers={'Origin':BASE,'Cookie':COOKIE,'Content-Type':'multipart/form-data; boundary='+boundary})
    with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)['id']
accounts=[]
try:
    alias=uuid.uuid4().hex[:12]
    for platform,external in [('x',str(uuid.uuid4().int)[:18]),('x','legacy-'+alias),('instagram',alias)]:
        code,a=action('account',platform=platform,handle='@'+platform+'-'+alias,lane='ambient',external_id=external,credential_ref='TEST_X_ACCOUNT',authorized=True,daily_limit=2)
        assert code==200;accounts.append(a['id'])
    media=upload();check(bool(media),'original X fixture media stored through owner API')
    payload=dict(title='Internal queue fixture',brief='Exact reviewed original video caption',account=accounts[0],asset=media,scheduled=int(time.time()*1000),approved=True,made_with_ai=True)
    check(action('publish',**payload)[0]==400,'X requires explicit account-audience approval')
    check(action('publish',**dict(payload,approved=False,approval_scope='x-account'))[0]==400,'unchecked publication approval rejected')
    payload['approval_scope']='x-account'
    check(action('publish',**dict(payload,account=accounts[1]))[0]==400,'X handle or legacy placeholder cannot replace numeric identity')
    check(action('publish',**dict(payload,account=accounts[2]))[0]==400,'unsupported provider cannot enter direct publishing')
    check(action('publish',**dict(payload,brief='😀'*141))[0]==400,'weighted caption overflow rejected before queueing')
    check(action('publish',**dict(payload,brief='bad\ufefftext'))[0]==400,'invalid X text rejected before queueing')
    check(action('publish',**dict(payload,made_with_ai='yes'))[0]==400,'AI-label field requires an explicit boolean')
    action('account-pause',id=accounts[0],paused=True)
    check(action('publish',**payload)[0]==400,'paused X account cannot queue a publication')
    action('account-pause',id=accounts[0],paused=False)
    payload['brief']='Original footage: https://example.com/'+'a'*350
    with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:action('publish',**payload),range(2)))
    check(sum(code==200 for code,_ in results)==1,'concurrent X approval creates exactly one queued publication')
    jid=next(v['id'] for code,v in results if code==200)
    rows=req(path='/api/control?q='+jid)[1]['jobs'];j=next(j for j in rows if j['id']==jid)
    check(j['brief']==payload['brief'] and j['made_with_ai']==1,'exact caption and AI-label choice persisted')
    check(j['approved']==1 and j['account']==accounts[0],'approval remains bound to the selected account')
    _,keys=action('worker-key');key=keys['token']
    code,c=req(dict(action='claim',request_id=str(uuid.uuid4())),token=key);j=c['job']
    check(code==200 and j['id']==jid and c['account']['platform']=='x','scoped worker receives the approved X task')
    check(req(dict(action='preflight',id=j['id'],lease=j['lease']),token=key)[0]==200,'X final preflight admits the current approved task')
    action('account-pause',id=accounts[0],paused=True)
    check(req(dict(action='preflight',id=j['id'],lease=j['lease']),token=key)[0]==409,'X account pause blocks final dispatch')
    action('account-pause',id=accounts[0],paused=False)
    check(req(dict(action='complete',id=j['id'],lease=j['lease'],status='uncertain',error='Fixture ambiguous X response; no provider call occurred',receipt='https://x.com/i/web/status/123456789'),token=key)[0]==200,'uncertain X result retains a candidate receipt')
    check(action('retry',id=jid)[0]==409,'uncertain X publication cannot be automatically retried')
    check(action('publish',**payload)[0]==409,'ambiguous X outcome retains the duplicate-publication lock')
    check(action('reconcile',id=jid,receipt='https://x.com/i/web/status/123456789')[0]==200,'operator can record a verified X receipt')
    j=next(j for j in req(path='/api/control?q='+jid)[1]['jobs'] if j['id']==jid)
    check(j['status']=='succeeded' and j['receipt'].endswith('123456789'),'reconciled X receipt remains inspectable')
finally:
    for aid in accounts:action('account-pause',id=aid,paused=True)
    action('revoke-key')
print(f'{checks} X publishing HTTP checks passed. No X/model API requests were made.')
