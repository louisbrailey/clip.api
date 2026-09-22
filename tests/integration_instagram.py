"""Loopback-only Instagram approval and queue checks. No Meta/model API requests are made."""
import concurrent.futures,http.cookiejar,json,time,urllib.error,urllib.request,uuid
from pathlib import Path
BASE='http://localhost:5173';jar=http.cookiejar.CookieJar();urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)).open(BASE+'/signin-with-chatgpt?return_to=/').read();COOKIE='; '.join(c.name+'='+c.value for c in jar);checks=0
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
def upload(i):
    boundary='instagram-'+uuid.uuid4().hex;media=Path('outputs/ambient-pink-noise.mp4').read_bytes()
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="rights"\r\n\r\noriginal\r\n--{boundary}\r\nContent-Disposition: form-data; name="evidence"\r\n\r\nOriginal local fixture media {i}.\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="instagram-{i}.mp4"\r\nContent-Type: video/mp4\r\n\r\n'.encode()+media+f'\r\n--{boundary}--\r\n'.encode())
    with urllib.request.urlopen(urllib.request.Request(BASE+'/api/assets',data=body,headers={'Origin':BASE,'Cookie':COOKIE,'Content-Type':'multipart/form-data; boundary='+boundary}),timeout=30) as response:return json.load(response)['id']
accounts=[]
try:
    alias=uuid.uuid4().hex[:12];external='178414'+str(uuid.uuid4().int)[:11]
    for value in (external,'ig-legacy-'+alias):
        code,a=action('account',platform='instagram',handle='@ig-'+alias+('-numeric' if value==external else ''),lane='ambient',external_id=value,credential_ref='TEST_INSTAGRAM',authorized=True,daily_limit=1);assert code==200;accounts.append(a['id'])
    picker=req(path='/api/control?picker=accounts&purpose=publish&q=ig-'+alias)[1]['items'];check(len(picker)==2 and {a['platform'] for a in picker}=={'instagram'},'Instagram appears in direct publishing account picker')
    media=upload(1);payload=dict(title='Instagram fixture reel',brief='Original Instagram reel caption',account=accounts[0],asset=media,scheduled=int(time.time()*1000),approved=True)
    check(action('publish',**payload)[0]==400,'Instagram requires an explicit account approval scope')
    check(action('publish',**dict(payload,approval_scope='youtube-private'))[0]==400,'wrong platform approval rejected')
    check(action('publish',**dict(payload,account=accounts[1],approval_scope='instagram-reel'))[0]==400,'numeric Instagram professional account ID required')
    payload['approval_scope']='instagram-reel'
    check(action('publish',**dict(payload,brief='x'*2201))[0]==400,'Instagram caption limit is rejected before queueing')
    with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:action('publish',**payload),range(2)))
    check(sum(code==200 for code,_ in results)==1,'concurrent Instagram approvals create exactly one job')
    jid=next(v['id'] for code,v in results if code==200);rows=req(path='/api/control?q='+jid)[1]['jobs'];j=next(x for x in rows if x['id']==jid)
    check(j['brief']==payload['brief'] and j['approved']==1 and j['account']==accounts[0],'exact Instagram approval and caption persisted')
    _,keys=action('worker-key');key=keys['token'];code,context=req(dict(action='claim',request_id=str(uuid.uuid4())),token=key);j=context['job']
    check(code==200 and j['id']==jid and context['account']['platform']=='instagram','worker receives approved Instagram task')
    check(req(dict(action='preflight',id=j['id'],lease=j['lease']),token=key)[0]==200,'Instagram preflight admits approved current lease')
    action('account-pause',id=accounts[0],paused=True);check(req(dict(action='preflight',id=j['id'],lease=j['lease']),token=key)[0]==409,'Instagram account pause blocks final publication');action('account-pause',id=accounts[0],paused=False)
    check(req(dict(action='complete',id=j['id'],lease=j['lease'],status='uncertain',error='Fixture interrupted Instagram publish',receipt='instagram-media:123456789'),token=key)[0]==200,'Instagram publication can enter uncertain recovery')
    check(action('retry',id=jid)[0]==409,'Instagram uncertain publication cannot be automatically retried')
    check(action('publish',**payload)[0]==409,'Instagram publication lock remains after uncertain outcome')
finally:
    for account in accounts:action('account-pause',id=account,paused=True)
    action('revoke-key')
print(f'{checks} Instagram publishing HTTP checks passed. No Meta/model API requests were made.')
