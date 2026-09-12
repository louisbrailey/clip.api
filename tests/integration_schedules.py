"""Loopback-only recurrence checks. Uses a disposable local identity and fixtures.
No model or social provider requests are made; completion payloads are test data.
"""
import concurrent.futures
import http.cookiejar
import json
import time
import urllib.error
import urllib.request
import uuid

BASE='http://localhost:5173'
jar=http.cookiejar.CookieJar()
urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)).open(BASE+'/signin-with-chatgpt?return_to=/').read()
COOKIE='; '.join(c.name+'='+c.value for c in jar)
checks=0
def check(value,label):
    global checks
    assert value,label;checks+=1;print('PASS',label)
def req(body=None,token=None,path='/api/control'):
    headers={'Origin':BASE,'Content-Type':'application/json'}
    headers.update({'Authorization':'Bearer '+token} if token else {'Cookie':COOKIE})
    request=urllib.request.Request(BASE+path,headers=headers,data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(request,timeout=20) as result:return result.status,json.load(result)
    except urllib.error.HTTPError as error:return error.code,json.load(error)
def action(action,**kwargs):return req(dict(action=action,**kwargs))
def state():return req()[1]
def claim(key):return req(dict(action='claim',request_id=str(uuid.uuid4())),token=key)
def schedule(id):return next(r for r in state()['schedules'] if r['id']==id)
def pause(id,value):
    r=schedule(id);return action('schedule-pause',id=id,revision=r['revision'],paused=value)
def edit(id,**changes):
    body=dict(schedule(id));body["paused"]=bool(body["paused"]);body.update(changes);return action('schedule',**body)
def complete(key,j,plan=False,status='succeeded'):
    body=dict(action='complete',id=j['id'],lease=j['lease'],status=status,tokens=50,result='Fixture original content')
    if plan:body['plan']=[dict(title='Write original script',brief='Write an original meditation for the specified account.',role='writer')]
    return req(body,token=key)
created=[]
try:
    _,token=action('worker-key');key=token['token']
    alias='same-'+uuid.uuid4().hex
    accounts=[]
    for platform in ['x','youtube']:
        code,a=action('account',platform=platform,handle='@'+alias,lane='ambient',external_id=alias,credential_ref='TEST_RECURRENCE',authorized=True,daily_limit=1)
        check(code==200,'account fixture saved');accounts.append(a['id'])
    production=req(path='/api/control?picker=accounts&purpose=production&q='+alias)[1]['items']
    check({a['platform'] for a in production}=={'youtube','x'},'production picker identifies both platforms')
    publication=req(path='/api/control?picker=accounts&q='+alias)[1]['items']
    check(len(publication)==1 and publication[0]['platform']=='youtube','publishing picker remains YouTube-only')
    start=int(time.time()*1000)-7200000
    payload=dict(request_id=str(uuid.uuid4()),account=accounts[0],title='Recurring integration meditation '+alias,brief='Create an original meditation for this account with a reviewable script.',mode='live',interval_minutes=60,next_run=start,max_runs=2,paused=False)
    check(action('schedule',**dict(payload,interval_minutes=1))[0]==400,'sub-hour recurrence rejected')
    check(action('schedule',**dict(payload,account=str(uuid.uuid4())))[0]==409,'missing account rejected')
    action('settings',paused=True,concurrency=4,daily_tokens=100000)
    code,r=action('schedule',**payload);check(code==200,'recurring schedule created');sid=r['id'];created.append(sid)
    check(action('schedule',**payload)[1]['id']==sid,'save replay returns original schedule')
    check(len([r for r in state()['schedules'] if r['id']==sid])==1,'save replay creates no duplicate')
    check(len([e for e in state()['events'] if e['message']=='Created recurring workflow: '+payload['title']])==1,'creation audit is atomic and not duplicated')
    check(claim(key)[1]['job'] is None and schedule(sid)['generated_count']==0,'workspace pause holds recurring generation')
    action('settings',paused=False,concurrency=4,daily_tokens=100000)
    action('account-pause',id=accounts[0],paused=True)
    check(claim(key)[1]['job'] is None and schedule(sid)['generated_count']==0,'account pause holds recurring generation')
    action('account-pause',id=accounts[0],paused=False)
    studio=next(a for a in state()['agents'] if a['id']=='ambient')
    action('agent',**dict(next(a for a in state()['agents'] if a['id']=='ambient'),paused=True))
    check(claim(key)[1]['job'] is None,'studio pause holds Astra account plans')
    action('agent',**dict(next(a for a in state()['agents'] if a['id']=='ambient'),paused=False))
    with concurrent.futures.ThreadPoolExecutor(2) as pool:claims=list(pool.map(lambda _:claim(key),range(2)))
    claimed=[result['job'] for code,result in claims if code==200 and result['job']]
    check(len(claimed)==1,'competing worker polls dispatch one occurrence')
    j=claimed[0];check(j['schedule_id']==sid and j['account']==accounts[0] and j['occurrence']==start,'root snapshots account and occurrence')
    check(schedule(sid)['generated_count']==1 and schedule(sid)['next_run']>int(time.time()*1000),'missed intervals coalesce and advance once')
    check(action('schedule-discard',id=sid,occurrence=start)[0]==409,'running occurrence cannot be discarded')
    before=state()['events']
    check(action('schedule-pause',id=sid,revision=1,paused=True)[0]==409,'stale control revision rejected')
    check(len(state()['events'])==len(before),'failed control creates no audit entry')
    check(pause(sid,True)[0]==200,'schedule pause saved')
    check(complete(key,j,plan=True)[0]==200,'running plan may finish while paused')
    check(claim(key)[1]['job'] is None,'paused schedule holds delegated children')
    jobs=req(path='/api/control?q='+sid)[1]['jobs']
    child=next(x for x in jobs if x['parent']==j['id'])
    check(child['account']==accounts[0] and child['schedule_id']==sid and child['occurrence']==start and child['approved']==0,'child retains account and schedule without publication approval')
    check(edit(sid,next_run=start)[0]==409,'editing to a used occurrence timestamp rejected')
    check(edit(sid,title='Future revised brief',brief='A revised original creative direction for future occurrences.',next_run=int(time.time()*1000)-10000,paused=False)[0]==200,'future schedule edited without changing the existing run')
    code,c=claim(key);check(code==200 and c['job']['id']==child['id'],'existing child runs with its saved context')
    check(c['account']['platform']=='x','worker receives correct account identity')
    check(complete(key,c['job'],status='failed')[0]==200,'failed child recorded')
    check(claim(key)[1]['job'] is None and schedule(sid)['generated_count']==1,'failed child holds future occurrences for review')
    check(action('schedule-discard',id=sid,occurrence=start)[0]==200,'waiting occurrence discarded after review')
    code,c=claim(key);check(code==200 and c['job']['title']=='Future revised brief','next occurrence uses revised creative direction')
    check(schedule(sid)['generated_count']==2,'second occurrence counted once')
    complete(key,c['job'],plan=True);_,c=claim(key);complete(key,c['job'])
    edit(sid,next_run=int(time.time()*1000)-5000)
    check(claim(key)[1]['job'] is None and schedule(sid)['generated_count']==2,'run limit stops recurring generation')
    rehearsal=dict(payload,request_id=str(uuid.uuid4()),mode='rehearsal',title='Recurring rehearsal fixture',max_runs=1)
    code,r=action('schedule',**rehearsal);check(code==200,'rehearsal schedule created');created.append(r['id'])
    check(claim(key)[1]['job'] is None,'live worker does not dispatch rehearsals')
    for _ in range(4):check(action('rehearse')[0]==200,'scheduled rehearsal step completed')
    rows=req(path='/api/control?q='+r['id'])[1]['jobs']
    check(len(rows)==4 and all(j['status']=='succeeded' for j in rows),'scheduled rehearsal completed all delegation steps')
    check(req(dict(action='schedule',**payload),token=key)[0]==403,'worker cannot create recurring operator instructions')
finally:
    for id in created:pause(id,True)
    action('settings',paused=False,concurrency=4,daily_tokens=100000)
    action('revoke-key')
print(f'{checks} recurrence HTTP checks passed. No model or social API requests were made.')
