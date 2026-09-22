"""Loopback-only proof of two recurring original videos, with fresh worker journals.

Uses a disposable local portal identity. No model or social provider requests.
"""
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

ROOT = Path(__file__).parents[1]
BASE = 'http://localhost:5173'
loader = importlib.util.spec_from_file_location('recurring_render_runtime', ROOT / 'worker/runtime.py')
r = importlib.util.module_from_spec(loader)
loader.loader.exec_module(r)
jar = http.cookiejar.CookieJar()
urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)).open(BASE + '/signin-with-chatgpt?return_to=/').read()
COOKIE = '; '.join(c.name + '=' + c.value for c in jar)
checks = 0
FFMPEG = os.environ['FFMPEG_BIN']
created = []


def check(ok, label):
    global checks
    assert ok, label
    checks += 1
    print('PASS', label, flush=True)


def req(body=None, key=None, path='/api/control', raw=None, extra=None):
    headers = {'Origin': BASE, 'Content-Type': 'application/json',
               **({'Authorization': 'Bearer ' + key} if key else {'Cookie': COOKIE}), **(extra or {})}
    data = raw if raw is not None else json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, headers=headers, data=data)
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def action(action_name, **kw):
    return req(dict(action=action_name, **kw))


def state():
    return req()[1]


def schedule(sid):
    return next(s for s in state()['schedules'] if s['id'] == sid)


def edit(sid, **changes):
    body = dict(schedule(sid))
    body['paused'] = bool(body['paused'])
    body['render_approved'] = bool(body['render_approved'])
    body['render_recipe'] = json.loads(body['render_recipe'])
    body.update(changes)
    return action('schedule', **body)


def pause(sid, value):
    return action('schedule-pause', id=sid, revision=schedule(sid)['revision'], paused=value)


def claim(key):
    return req(dict(action='claim', request_id=str(uuid.uuid4())), key=key)


def job(jid):
    return next(j for j in req(path='/api/control?q=' + jid)[1]['jobs'] if j['id'] == jid)


def editor_pause(value):
    editor = next(a for a in state()['agents'] if a['id'] == 'ambient-editor')
    return action('agent', **dict(editor, paused=value))


try:
    alias = 'recurring-video-' + uuid.uuid4().hex
    accounts = []
    for lane in ('ambient', 'gaming'):
        code, a = action('account', platform='youtube', handle='@' + alias + lane, lane=lane,
                         external_id=alias + lane, credential_ref='TEST_RECURRING_VIDEO', authorized=True, daily_limit=1)
        check(code == 200, lane + ' account fixture saved')
        accounts.append(a['id'])
    start = int(time.time() * 1000) - 7200000
    payload = dict(request_id=str(uuid.uuid4()), account=accounts[0], title='Recurring original video fixture',
                   brief='Create an original soundscape using the approved recurring recipe.', mode='live',
                   production_kind='ambient', render_recipe=dict(seconds=10, noise='pink', theme='ocean'),
                   render_approved=True, interval_minutes=60, next_run=start, max_runs=2, paused=False)
    check(action('schedule', **dict(payload, render_approved=False))[0] == 400, 'recurring rendering requires explicit recipe approval')
    check(action('schedule', **dict(payload, mode='rehearsal'))[0] == 400, 'recurring rendering cannot masquerade as a rehearsal')
    check(action('schedule', **dict(payload, render_recipe=dict(seconds=301, noise='pink', theme='ocean')))[0] == 400, 'out-of-bounds recurring recipe rejected')
    check(action('schedule', **dict(payload, account=accounts[1]))[0] == 409, 'ambient output requires an ambient account')
    code, saved = action('schedule', **payload)
    check(code == 200, 'approved recurring original video schedule saved')
    sid = saved['id']
    created.append(sid)
    check(action('schedule', **payload)[1]['id'] == sid, 'exact creation replay returns the same schedule')
    check(action('schedule', **dict(payload, render_recipe=dict(seconds=10, noise='brown', theme='forest')))[0] == 409, 'creation replay rejects a changed recipe')
    _, granted = action('worker-key')
    key = granted['token']
    check(req(dict(action='schedule', **payload), key=key)[0] == 403, 'worker cannot approve a recurring recipe')
    editor_pause(True)
    check(claim(key)[1]['job'] is None and schedule(sid)['generated_count'] == 0, 'paused renderer holds occurrence expansion')
    editor_pause(False)
    action('account-pause', id=accounts[0], paused=True)
    check(claim(key)[1]['job'] is None and schedule(sid)['generated_count'] == 0, 'paused account holds recurring rendering')
    action('account-pause', id=accounts[0], paused=False)
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        claims = list(pool.map(lambda _: claim(key), range(2)))
    active = [result for code, result in claims if code == 200 and result['job']]
    check(len(active) == 1, 'competing worker polls create and claim only one video occurrence')
    first_context = active[0]
    first = first_context['job']
    spec = first['render_spec']
    parsed = json.loads(spec)
    check(first['kind'] == 'render' and first['agent'] == 'ambient-editor' and first['reserve'] == 0 and first['approved'] == 1, 'approved recurrence dispatches a render with no model reservation')
    check(first['account'] == accounts[0] and first['schedule_id'] == sid and first['occurrence'] == start and 1 <= parsed['seed'] <= 2147483647, 'first occurrence stores its account, schedule, time and generated seed')
    check(schedule(sid)['generated_count'] == 1 and schedule(sid)['next_run'] > int(time.time() * 1000), 'missed intervals coalesce into one video run')
    check(action('schedule', **payload)[1]['id'] == sid and schedule(sid)['generated_count'] == 1, 'creation replay after expansion preserves the existing run')
    pre = dict(action='render-preflight', id=first['id'], lease=first['lease'])
    pause(sid, True)
    check(req(pre, key=key)[0] == 409, 'schedule pause fences a claimed render preflight')
    check(req(path='/api/render', key=key, raw=b'', extra={'X-Render-Job': first['id'], 'X-Render-Lease': first['lease']})[0] == 409, 'schedule pause also fences generated media registration')
    check(edit(sid, production_kind='workflow', render_recipe=None, render_approved=False)[0] == 409, 'schedule output type cannot change after creation')
    second_time = int(time.time() * 1000) - 10000
    recipe2 = dict(seconds=10, noise='brown', theme='forest')
    check(edit(sid, title='Revised recurring forest video', render_recipe=recipe2, render_approved=False)[0] == 400, 'editing a recipe requires renewed approval')
    check(edit(sid, title='Revised recurring forest video', render_recipe=recipe2, next_run=second_time, paused=False)[0] == 200, 'approved recipe revision applies to a future occurrence')
    check(job(first['id'])['render_spec'] == spec and job(first['id'])['title'] == payload['title'], 'claimed occurrence keeps its original saved recipe and title')
    check(claim(key)[1]['job'] is None and schedule(sid)['generated_count'] == 1, 'unfinished first video holds the next occurrence')
    records = []
    with patch.dict(os.environ, {'PATH': os.environ.get('PATH', ''), 'FFMPEG_BIN': FFMPEG}, clear=True):
        portal = r.Portal(BASE, key)
        for index in range(2):
            context = first_context if index == 0 else claim(key)[1]
            current = context['job']
            if index == 1:
                parsed2 = json.loads(current['render_spec'])
                check(current['occurrence'] == second_time and current['id'] != first['id'] and all(parsed2[k] == v for k, v in recipe2.items()), 'next occurrence snapshots the revised recipe into a distinct job')
            # Each run starts a fresh Worker and local journal, exercising portal persistence.
            with tempfile.TemporaryDirectory() as journal:
                r.Worker(portal, r.Journal(journal)).process(context)
            finished = job(current['id'])
            check(finished['status'] == 'succeeded' and bool(finished['asset']), 'fresh worker completes recurring video ' + str(index + 1))
            asset = next(a for a in state()['assets'] if a['id'] == finished['asset'])
            video = portal.media(asset['id'])
            check(hashlib.sha256(video).hexdigest() == asset['sha256'] and asset['source_job'] == current['id'] and asset['rights'] == 'original', 'recurring video ' + str(index + 1) + ' retains verified original provenance')
            output = ROOT / ('outputs/ambient-recurring-' + ('ocean' if index == 0 else 'forest') + '.mp4')
            output.write_bytes(video)
            subprocess.run([FFMPEG, '-hide_banner', '-loglevel', 'error', '-i', str(output), '-f', 'null', '-'], check=True, timeout=60, capture_output=True)
            check(True, 'recurring video ' + str(index + 1) + ' fully decodes')
            output.with_suffix('.rights.json').write_text(json.dumps({k: asset[k] for k in ('id', 'name', 'source_job', 'sha256', 'rights', 'evidence', 'expires')}, indent=2) + '\n')
            records.append(dict(job_id=current['id'], occurrence=current['occurrence'], recipe=json.loads(current['render_spec']), asset_id=asset['id'], sha256=asset['sha256'], bytes=len(video), output=output.name))
    check(schedule(sid)['generated_count'] == 2, 'two completed occurrences counted exactly once each')
    edit(sid, next_run=int(time.time() * 1000) - 5000)
    check(claim(key)[1]['job'] is None and schedule(sid)['generated_count'] == 2, 'recurring video run limit prevents a third occurrence')
    rows = req(path='/api/control?q=' + sid)[1]['jobs']
    check(len(rows) == 2 and all(j['kind'] == 'render' for j in rows), 'recurring videos do not implicitly create model or publication jobs')
    (ROOT / 'outputs/recurring-render-proof.json').write_text(json.dumps(dict(environment='disposable loopback portal; no provider calls', schedule_id=sid, checks=checks, occurrences=records), indent=2) + '\n')
finally:
    for sid in created:
        pause(sid, True)
    editor_pause(False)
    action('revoke-key')
print(f'{checks} recurring render HTTP checks passed, including two actual videos and fresh worker journals. No model/social API requests.')
