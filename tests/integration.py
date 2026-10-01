"""Local-only HTTP integration checks. Never run against a production Site.
Run after migrations with `npm run dev` on localhost:5173.
"""
import concurrent.futures
import http.cookiejar
import json
from pathlib import Path
import urllib.request
import urllib.error
import uuid
import time

BASE='http://localhost:5173'
jar=http.cookiejar.CookieJar();session=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
session.open(BASE+'/signin-with-chatgpt?return_to=/').read()
COOKIE='; '.join(c.name+'='+c.value for c in jar)
checks=0

def check(ok,message):
    global checks
    assert ok,message;checks+=1;print('PASS',message)
def req(body=None,token=None,path='/api/control',auth=True,origin=BASE):
    headers={'Origin':origin}
    if token:headers['Authorization']='Bearer '+token
    elif auth:headers['Cookie']=COOKIE
    if body is not None:headers['Content-Type']='application/json'
    r=urllib.request.Request(BASE+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    try:
        with urllib.request.urlopen(r) as result:return result.status,json.load(result)
    except urllib.error.HTTPError as e:
        try:body=json.load(e)
        except ValueError:body={}
        return e.code,body
def action(a,**v):return req({'action':a,**v})
def claim(key,request_id=None):return req({'action':'claim','request_id':request_id or str(uuid.uuid4())},token=key)
def state():return req()[1]
def completion(j,result='complete',plan=None):
    value={'action':'complete','id':j['id'],'lease':j['lease'],'status':'succeeded','result':result,'tokens':50}
    if plan:value['plan']=plan
    return value
plan1=[{'title':'Write a script','brief':'Create an original breathing script.','role':'writer'}]
plan2=plan1+[{'title':'Review script','brief':'Review the original breathing script.','role':'editor'}]
root_ids=[]
try:
    check(req(auth=False)[0]==401,'unauthenticated APIs rejected')
    check(req(token='invalid')[0]==401,'invalid worker keys rejected')
    check(req({'action':'workflow'},origin='https://evil.example')[0]==403,'cross-origin writes rejected')
    check(len(state()['agents'])==13,'initial Astra tree has 13 configured agents')
    for title,brief in [('Integration rehearsal','Create an original breathing script and editorial brief.'),('x'*160,'b'*6000)]:
        code,v=action('workflow',title=title,brief=brief,lane='ambient',mode='rehearsal');check(code==200,'rehearsal accepted');root_ids.append(v['id'])
        for _ in range(4):check(action('rehearse')[0]==200,'rehearsal dispatch and completion')
        rows=[j for j in state()['jobs'] if j['id']==v['id'] or j['parent']==v['id']]
        check(len(rows)==4 and all(j['status']=='succeeded' for j in rows),'Astra plan and all three dependent tasks completed')
    check(req(path='/api/control?q='+'a'*120)[0]==200,'long searches do not exceed D1 LIKE limits')
    _,v=action('worker-key');key=v['token']
    check(req(token=key)[0]==403,'worker cannot read browser control room')
    check(req({'action':'workflow','title':'blocked'},token=key)[0]==403,'worker cannot create operator workflows')
    code,v=action('workflow',title='Live callback race test',brief='Produce an original script for a calm morning meditation.',lane='ambient',mode='live');root_ids.append(v['id'])
    request_id=str(uuid.uuid4());code,c=claim(key,request_id);j=c['job'];check(code==200 and j['id']==v['id'],'live claim retrieves expected job')
    check(c['agent']['model']=='gpt-6-astra','Astra model preserved in worker context')
    check(claim(key,request_id)[1]['job']['id']==j['id'],'ambiguous claim retry returns same lease')
    _,second=action('worker-create',name='Isolation fixture',concurrency=1);second_key=second['token'];second_worker=second['worker']
    check(req({'action':'heartbeat','id':j['id'],'lease':j['lease']},token=second_key)[0]==409,'another worker cannot renew a foreign lease')
    check(req(completion(j,'foreign completion',plan1),token=second_key)[0]==409,'another worker cannot complete a foreign lease')
    check(action('worker-control',id=second_worker['id'],revision=second_worker['revision'],name=second_worker['name'],paused=True,concurrency=1)[0]==200,'individual worker pause is saved')
    check(claim(second_key)[1]['job'] is None,'paused worker cannot claim tasks')
    second_worker=next(w for w in state()['workers'] if w['id']==second_worker['id'])
    check(action('worker-revoke',id=second_worker['id'],revision=second_worker['revision'])[0]==200,'individual worker can be revoked')
    check(claim(second_key)[0]==401,'revoked individual worker loses access')
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda body:req(body,token=key),[completion(j,'plan one',plan1),completion(j,'plan two',plan2)]))
    check(sorted(x[0] for x in results)==[200,409],'competing completion has a single winner')
    latest=state();root=next(x for x in latest['jobs'] if x['id']==j['id']);children=[x for x in latest['jobs'] if x['parent']==j['id']]
    expected=1 if root['result']=='plan one' else 2
    check(len(children)==expected,'losing completion cannot append extra children')
    winning=completion(j,root['result'],plan1 if expected==1 else plan2)
    check(req(winning,token=key)[0]==200,'identical completion retry is idempotent')
    winning['lease']=str(uuid.uuid4());check(req(winning,token=key)[0]==409,'stale lease completion rejected')
    check(all(x['lease'] is None for x in latest['jobs']),'lease credentials omitted from browser payload')
    charged=latest['tokens_today'];check(charged==50,'idempotent completion charges usage only once')
    action('settings',paused=True,concurrency=4,daily_tokens=100000)
    check(claim(key)[1]['job'] is None,'global pause blocks new machine dispatch')
    action('settings',paused=False,concurrency=4,daily_tokens=100000)
    a=next(a for a in state()['agents'] if a['id']=='ambient')
    action('agent',revision=next(v for v in state()['agents'] if v['id']==a['id'])['revision'],id=a['id'],model=a['model'],concurrency=a['concurrency'],instructions=a['instructions'],paused=True)
    check(claim(key)[1]['job'] is None,'studio pause blocks descendant tasks')
    action('agent',revision=next(v for v in state()['agents'] if v['id']==a['id'])['revision'],id=a['id'],model=a['model'],concurrency=a['concurrency'],instructions=a['instructions'],paused=False)
    while True:
        code,c=claim(key)
        if not c['job']:break
        check(req(completion(c['job'],'Original completed test output'),token=key)[0]==200,'child tasks complete with fenced leases')
    # Upload a real generated MP4 through the normal authenticated media API.
    file=Path('outputs/ambient-pink-noise.mp4');boundary='constellation-'+uuid.uuid4().hex
    parts=[]
    for name,value in {'rights':'original','evidence':'Original procedural color video and synthesized pink noise generated by the bundled renderer.'}.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts += [f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="ambient-test.mp4"\r\nContent-Type: video/mp4\r\n\r\n'.encode(),file.read_bytes(),f'\r\n--{boundary}--\r\n'.encode()]
    upload=urllib.request.Request(BASE+'/api/assets',data=b''.join(parts),headers={'Origin':BASE,'Cookie':COOKIE,'Content-Type':'multipart/form-data; boundary='+boundary})
    with urllib.request.urlopen(upload) as r:asset=json.load(r)['id'];check(r.status==200,'real MP4 and rights record stored')
    with urllib.request.urlopen(urllib.request.Request(BASE+'/api/assets/'+asset,headers={'Cookie':COOKIE,'Range':'bytes=0-15'})) as r:
        check(r.status==206 and len(r.read())==16,'authenticated media supports byte ranges')
    code,a=action('account',platform='youtube',handle='@integration-test',lane='ambient',external_id='test-'+uuid.uuid4().hex,credential_ref='TEST_YOUTUBE',authorized=True,daily_limit=1)
    check(code==200,'authorized account registration works')
    upload_body={'action':'publish','title':'Private integration upload','brief':'Original test media; no provider request will be made.','account':a['id'],'asset':asset,'scheduled':int(time.time()*1000),'approved':True}
    with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:req(upload_body),range(2)))
    check(sum(code==200 for code,_ in results)==1,'simultaneous approvals create exactly one publication')
    code,c=claim(key);pj=c['job'];check(pj['kind']=='publish','approved upload becomes claimable')
    check(req({'action':'preflight','id':pj['id'],'lease':pj['lease']},token=key)[0]==200,'publishing preflight authorizes current payload')
    action('account-pause',id=a['id'],paused=True)
    check(req({'action':'preflight','id':pj['id'],'lease':pj['lease']},token=key)[0]==409,'pause before provider dispatch blocks upload')
    check(req({'action':'complete','id':pj['id'],'lease':pj['lease'],'status':'uncertain','error':'Simulated lost provider response'},token=key)[0]==200,'ambiguous upload enters uncertain state')
    check(action('retry',id=pj['id'])[0]==409,'uncertain publication cannot be blindly retried')
    check(action('reconcile',id=pj['id'],receipt='integration-only-no-real-upload')[0]==200,'operator can record a verified receipt')
    action('revoke-key');check(claim(key)[0]==401,'revoked machine key loses access immediately')
finally:
    action('settings',paused=False,concurrency=4,daily_tokens=100000)
    action('revoke-key')
print(f'{checks} HTTP integration checks passed. No model or social API calls were made.')
