"""Loopback-only network API regressions. Run after existing integration suites.
Uses disposable local records and fixture completions, never provider calls.
"""
import base64
import http.cookiejar
import json
import urllib.error
import urllib.parse
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
def req(body=None,path='/api/agents',token=None,auth=True,origin=BASE):
    headers={'Origin':origin,'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    elif auth:headers['Cookie']=COOKIE
    request=urllib.request.Request(BASE+path,headers=headers,data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(request,timeout=30) as result:return result.status,json.load(result)
    except urllib.error.HTTPError as error:
        try:body=json.load(error)
        except ValueError:body={}
        return error.code,body
def action(action,**v):return req(dict(action=action,**v))
def control(action,**v):return req(dict(action=action,**v),path='/api/control')
def branch(id):return req(path='/api/agents?focus='+id)[1]
def config(id):return branch(id)['focus']
def update(id,paused):
    a=config(id);return action('update',**dict(a,paused=paused))
def route(agent=None,account=None,revision=0):return action('route',lane='ambient',role='writer',agent=agent,account=account,revision=revision)
def references(id,after=''):return req(path='/api/agents?references='+id+'&after='+urllib.parse.quote(after))[1]
def retire(id,archived=True):return action('retire',id=id,revision=config(id)['revision'],archived=archived)
def claim(key):return req(dict(action='claim',request_id=str(uuid.uuid4())),path='/api/control',token=key)[1]['job']
def complete(key,j,plan=None):
    body=dict(action='complete',id=j['id'],lease=j['lease'],status='succeeded',tokens=50,result='Original fixture output')
    if plan:body['plan']=plan
    return req(body,path='/api/control',token=key)
def create(parent='ambient',name='Network writer',paused=False,**extra):
    body=dict(request_id=str(uuid.uuid4()),parent=parent,name=name,task_role='writer',model='gpt-5.6-sol',instructions='Write distinct original meditation scripts with accurate source records.',concurrency=1,paused=paused)
    body.update(extra);return body,action('create',**body)
prefix='Network '+uuid.uuid4().hex[:8]+' '
accounts=[]
studio_revision=0
try:
    check(req(auth=False)[0]==401,'network reads require authentication')
    check(req(dict(action='create'),origin='https://evil.example')[0]==403,'network mutations reject cross-origin requests')
    _,k=control('worker-key');key=k['token']
    check(req(token=key)[0]==403,'worker cannot inspect agent registry')
    check(req(dict(action='create'),token=key)[0]==403,'worker cannot alter agent registry')
    check(len(branch('astra')['children'])==4,'initial root exposes four studio branches')
    check(create(parent='astra')[1][0]==409,'new agents must belong to a studio branch')
    check(create(parent='missing')[1][0]==409,'nonexistent parent rejected')
    initial=branch('astra')['total']
    body,(code,v)=create(name=prefix+'Écho writer',paused=True);writer=v['id']
    check(code==200 and config(writer)['depth']==2,'custom writer created under the selected studio')
    check(action('create',**body)[1]['id']==writer and branch('astra')['total']==initial+1,'creation replay retains one configuration and count')
    check(config(writer)['route_count']==0,'new agent starts without production assignments')
    _,(code,v)=create(name=prefix+'Other writer');override=v['id'];check(code==200,'second routing target created')
    check(route(agent=writer)[0]==200,'studio writer assignment saved');studio_revision=1
    check(route(agent=override)[0]==409,'stale assignment creation rejected')
    check(retire(writer)[0]==409,'assigned agent cannot be retired')
    alias=uuid.uuid4().hex
    for lane in ['ambient','sports']:
        code,v=control('account',platform='x',handle='@network-'+lane+'-'+alias,lane=lane,external_id=lane+'-'+alias,credential_ref='TEST_NETWORK',authorized=True,daily_limit=1)
        assert code==200;accounts.append(v['id'])
    check(route(agent=override,account=accounts[1])[0]==409,'wrong studio account assignment rejected')
    check(action('route',lane='ambient',role='editor',account=None,agent=writer,revision=0)[0]==409,'wrong task-role assignment rejected')
    check(route(agent=override,account=accounts[0])[0]==200,'account-specific writer assignment saved')
    control('account-pause',id=accounts[0],paused=True)
    picker=req(path='/api/control?picker=accounts&purpose=routing&lane=ambient&q='+alias)[1]['items']
    check([r['id'] for r in picker]==[accounts[0]],'routing picker includes paused accounts and filters by studio')
    control('account-pause',id=accounts[0],paused=False)
    check(references(override)['items'][0]['handle'].startswith('@network-ambient'),'assignment references identify the account')
    # A manual live workflow has no account; use the studio override and hold it while paused.
    _,v=control('workflow',title='Network assignment fixture',brief='Write an original meditation script.',lane='ambient',mode='live')
    j=claim(key);check(j['id']==v['id'] and j['agent']=='astra','Astra retains root orchestration')
    plan=[dict(title='Assigned original script',brief='Write an original short meditation.',role='writer')]
    check(complete(key,j,plan)[0]==200,'Astra fixture delegates through the studio route')
    queued=req(path='/api/control?q='+writer)[1]['jobs']
    child=next(c for c in queued if c['parent']==j['id'])
    check(child['agent']==writer and claim(key) is None,'paused explicit target holds delegated work without fallback')
    stale=config(writer)
    check(update(writer,False)[0]==200,'custom writer resumed')
    check(action('update',**dict(stale,paused=False))[0]==409,'stale agent control revision rejected')
    j=claim(key);check(j['id']==child['id'],'custom configured agent receives its assigned task')
    check(retire(writer)[0]==409,'running custom agent cannot be retired')
    check(complete(key,j)[0]==200,'custom agent fixture completion accepted')
    check(config(writer)['running']==0 and config(writer)['queued']==0,'node task counters refresh after completion')
    check(route(agent=None,revision=1)[0]==200,'studio assignment reset');studio_revision=2
    check(route(agent=writer,revision=0)[0]==409,'reset preserves revision history and rejects ABA replay')
    check(retire(writer)[0]==200,'unassigned agent with completed work can retire')
    check(update(writer,False)[0]==409,'retired agent controls rejected')
    check(create(parent=writer)[1][0]==409,'retired agent cannot gain children')
    update('ambient',True)
    check(retire(writer,False)[0]==409,'restore blocked under paused ancestor')
    update('ambient',False)
    check(retire(writer,False)[0]==200 and config(writer)['paused']==1,'restore keeps agent paused')
    check(retire('ambient')[0]==409,'built-in studio cannot retire')
    # 25 same-prefix children exercise both independently bounded page surfaces.
    ids=[]
    for i in range(25):
        _,(code,v)=create(parent=override,name=prefix+'Repeated writer');assert code==200;ids.append(v['id'])
    b=branch(override);check(len(b['children'])==12 and b['focus']['child_count']==25,'branch response is bounded to twelve children')
    all_ids=[];after=''
    while True:
        b=req(path='/api/agents?focus='+override+'&after='+after)[1];all_ids.extend(c['id'] for c in b['children'])
        if not b['next']:break
        after=b['next']
    check(len(all_ids)==len(set(all_ids))==25 and set(all_ids)==set(ids),'child keyset pagination has no omissions or duplicates')
    matches=[];after=''
    while True:
        r=req(path='/api/agents?search='+urllib.parse.quote(prefix.strip())+'&after='+urllib.parse.quote(after))[1]
        assert len(r['items'])<=20;matches.extend(x['id'] for x in r['items'])
        if not r['next']:break
        after=r['next']
    check(len(matches)==len(set(matches))==27,'prefix search pagination includes Unicode and duplicate names')
    bad=base64.b64encode(json.dumps(['elsewhere','foreign']).encode()).decode()
    check(req(path='/api/agents?search=network&after='+urllib.parse.quote(bad))[0]==400,'search cursor from a different prefix rejected')
    check(req(path='/api/agents?search='+urllib.parse.quote(chr(0x10ffff)))[0]==200,'maximum Unicode prefix handled without server error')
    check(len(req(path='/api/control')[1]['agents'])==13,'regular workspace poll remains bounded to built-in agents')
    check(retire(override)[0]==409,'nonretired child configurations protect their parent')
    parent=ids[0]
    for depth in range(4,9):
        _,(code,v)=create(parent=parent,name=prefix+'Depth '+str(depth));assert code==200;parent=v['id']
    check(config(parent)['depth']==8 and len(branch(parent)['ancestors'])==8,'deep ancestry is bounded and preserved')
    check(create(parent=parent)[1][0]==409,'ninth-level configuration rejected')
    check(retire(parent)[0]==200,'unassigned deep leaf can retire')
finally:
    for aid in accounts:control('account-pause',id=aid,paused=True)
    if accounts:route(agent=None,account=accounts[0],revision=1)
    if studio_revision==1:route(agent=None,revision=1)
    update('ambient',False)
    control('settings',paused=False,concurrency=4,daily_tokens=100000)
    control('revoke-key')
print(f'{checks} network HTTP checks passed. No model or social API requests were made.')
