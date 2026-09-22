"""Loopback-only Threads approval and queue checks. No Threads/model API requests are made."""
import concurrent.futures,http.cookiejar,json,time,urllib.error,urllib.request,uuid
from pathlib import Path
BASE='http://localhost:5173';jar=http.cookiejar.CookieJar();urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)).open(BASE+'/signin-with-chatgpt?return_to=/').read();COOKIE='; '.join(c.name+'='+c.value for c in jar);checks=0;URL='https://staging.example.com/original-video.mp4?sig=fixture'
def check(ok,label):
    global checks
    assert ok,label;checks+=1;print('PASS',label)
def req(body=None,token=None,path='/api/control'):
    headers={'Origin':BASE,'Content-Type':'application/json'};headers.update({'Authorization':'Bearer '+token} if token else {'Cookie':COOKIE});request=urllib.request.Request(BASE+path,headers=headers,data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(request,timeout=30) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:
        try:v=json.load(e)
        except ValueError:v={}
        return e.code,v
def action(name,**kw):return req(dict(action=name,**kw))
accounts=[]
try:
    alias=uuid.uuid4().hex[:12];external='178414'+str(uuid.uuid4().int)[:11]
    for value in (external,'threads-legacy-'+alias):
        code,a=action('account',platform='threads',handle='@threads-'+alias,lane='ambient',external_id=value,credential_ref='TEST_THREADS',authorized=True,daily_limit=1);assert code==200;accounts.append(a['id'])
    picker=req(path='/api/control?picker=accounts&purpose=publish&q=threads-'+alias)[1]['items'];check(len(picker)==2 and {a['platform'] for a in picker}=={'threads'},'Threads appears in direct publishing account picker')
    boundary='threads-'+uuid.uuid4().hex;media=Path('outputs/ambient-pink-noise.mp4').read_bytes();body=(f'--{boundary}\r\nContent-Disposition: form-data; name="rights"\r\n\r\noriginal\r\n--{boundary}\r\nContent-Disposition: form-data; name="evidence"\r\n\r\nOriginal local fixture media.\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="threads.mp4"\r\nContent-Type: video/mp4\r\n\r\n'.encode()+media+f'\r\n--{boundary}--\r\n'.encode())
    with urllib.request.urlopen(urllib.request.Request(BASE+'/api/assets',data=body,headers={'Origin':BASE,'Cookie':COOKIE,'Content-Type':'multipart/form-data; boundary='+boundary}),timeout=30) as response:asset=json.load(response)['id']
    payload=dict(title='Threads internal fixture',brief='Exact Threads text',account=accounts[0],asset=asset,scheduled=int(time.time()*1000),approved=True,media_url=URL)
    check(action('publish',**payload)[0]==400,'Threads requires an explicit account approval scope')
    check(action('publish',**dict(payload,approval_scope='instagram-reel'))[0]==400,'wrong Threads approval scope rejected')
    check(action('publish',**dict(payload,account=accounts[1],approval_scope='threads-post'))[0]==400,'numeric Threads account ID required')
    check(action('publish',**dict(payload,approval_scope='threads-post',media_url=None))[0]==400,'fixture requires public media URL');payload['approval_scope']='threads-post'
    check(action('publish',**dict(payload,media_url='http://localhost/private.mp4'))[0]==400,'non-HTTPS staging URL rejected before queueing');payload['media_url']=URL
    check(action('publish',**dict(payload,brief='x'*501))[0]==400,'Threads text limit rejected before queueing')
    with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:action('publish',**payload),range(2)))
    check(sum(code==200 for code,_ in results)==1,'concurrent Threads approvals create exactly one job')
    jid=next(v['id'] for code,v in results if code==200);j=next(x for x in req(path='/api/control?q='+jid)[1]['jobs'] if x['id']==jid)
    check(j['brief']==payload['brief'] and j['media_url']==URL and j['approved']==1,'exact Threads text and staging URL persisted')
    _,keys=action('worker-key');key=keys['token'];code,context=req(dict(action='claim',request_id=str(uuid.uuid4())),token=key);j=context['job']
    check(code==200 and j['id']==jid and context['account']['platform']=='threads','worker receives approved Threads task')
    check(req(dict(action='preflight',id=j['id'],lease=j['lease']),token=key)[0]==200,'Threads preflight admits approved current lease')
    action('account-pause',id=accounts[0],paused=True);check(req(dict(action='preflight',id=j['id'],lease=j['lease']),token=key)[0]==409,'Threads account pause blocks final publication');action('account-pause',id=accounts[0],paused=False)
    check(req(dict(action='complete',id=j['id'],lease=j['lease'],status='uncertain',error='Fixture interrupted Threads publish',receipt='threads-media:123456789'),token=key)[0]==200,'Threads publication can enter uncertain recovery')
    check(action('retry',id=jid)[0]==409,'Threads uncertain publication cannot be automatically retried')
    check(action('publish',**payload)[0]==409,'Threads publication lock remains after uncertain outcome')
finally:
    for account in accounts:action('account-pause',id=account,paused=True)
    action('revoke-key')
print(f'{checks} Threads publishing HTTP checks passed. No Threads/model API requests were made.')
