"""Network lifecycle and routing regressions using actual application SQL."""
import unittest
import sqlite3
import pathlib
import re
import json
import uuid

root = pathlib.Path(__file__).resolve().parents[1]
network = (root / 'lib/network.ts').read_text()
control = (root / 'app/api/control/route.ts').read_text()

def template_in_function(name):
    section = network.split('export async function ' + name + '(', 1)[1].split('export async function ', 1)[0]
    return re.search(r'sql\(\s*`([^`]+)`', section, re.S).group(1)

CREATE = template_in_function('createAgent')
ROUTE = template_in_function('setRoute')
RETIRE, RESTORE = re.search(r'const query\s*=\s*v.archived\s*\?\s*`([^`]+)`\s*:\s*`([^`]+)`', network, re.S).groups()
strings = [json.loads(s) for s in re.findall(r'sql\(\s*("(?:[^"\\]|\\.)*")', network)]
CHILD_COUNTER = next(s for s in strings if s.startswith('UPDATE agents SET child_count'))
TOTAL_COUNTER = next(s for s in strings if s.startswith('UPDATE settings SET agent_total'))
COMPLETION = next(json.loads(s) for s in re.findall(r'sql\(\s*("(?:[^"\\]|\\.)*")', control) if s.startswith('"INSERT OR IGNORE INTO jobs(id,owner,parent,depends,agent,'))
checks = 0

def check(condition, label):
    global checks
    assert condition, label
    checks += 1

def fixture():
    c = sqlite3.connect(':memory:')
    c.row_factory = sqlite3.Row
    for p in sorted((root / 'drizzle').glob('*.sql')):
        c.executescript(p.read_text())
    for owner in ['own', 'other']:
        c.execute('INSERT INTO settings(owner,agent_total) VALUES(?,13)', (owner,))
        rows = [('astra', None, 'all', 'orchestrator', 0, 4)]
        rows += [(lane, 'astra', lane, 'lead', 1, 2) for lane in ['ambient', 'gaming', 'originals', 'sports']]
        rows += [(lane + '-' + role, lane, lane, role, 2, 0) for lane in ['ambient', 'gaming', 'originals', 'sports'] for role in ['writer', 'editor']]
        for aid, parent, lane, role, depth, count in rows:
            c.execute('INSERT INTO agents(owner,id,parent,name,role,lane,model,instructions,color,task_role,core,depth,child_count,search_name) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (owner, aid, parent, aid, role, lane, 'test', 'instruct', '#fff', role, 1, depth, count, aid))
    c.commit()
    return c

def create(c, aid, parent='ambient', owner='own', role='writer'):
    with c:
        n = c.execute(CREATE, (owner, aid, aid, role, 'model', 0, 1, 'instructions', role, aid.lower(), owner, parent)).rowcount
        c.execute(CHILD_COUNTER, (owner, parent))
        c.execute(TOTAL_COUNTER, (owner,))
    return n

def route(c, aid, rev=0, owner='own', role='writer', lane='ambient', account=None):
    scope = 'account:' + account if account else 'studio:' + lane
    return c.execute(ROUTE, (owner, scope, role, aid, rev, owner, scope, role, aid, owner, aid, lane, role, account, owner, account, lane, rev)).rowcount

def lifecycle(c, aid, archive=True, rev=1, owner='own'):
    return c.execute(RETIRE if archive else RESTORE, (owner, aid, rev)).rowcount

def account(c, owner='own', lane='ambient'):
    aid = str(uuid.uuid4())
    c.execute('INSERT INTO accounts(id,owner,platform,handle,lane,external_id,credential_ref,authorized,created) VALUES(?,?,?,?,?,?,?,?,?)',
              (aid, owner, 'youtube', aid, lane, aid, 'TEST_REF', 1, 0))
    return aid

def complete_child(c, owner='own', account_id=None, role='writer', nonce='won', requested_nonce='won'):
    jid = str(uuid.uuid4())
    cid = jid + '-0'
    lane = 'ambient'
    fallback = lane if role == 'lead' else lane + '-' + role
    c.execute('INSERT INTO jobs(id,owner,agent,title,brief,lane,kind,mode,status,created,scheduled,completion_nonce) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
              (jid, owner, 'astra', 'plan', 'brief', lane, 'plan', 'rehearsal', 'succeeded', 1, 1, nonce))
    binds = (cid, owner, jid, None, owner, 'account:' + account_id if account_id else 'none', role, owner, 'studio:' + lane, role, fallback,
             'child', 'brief', lane, 'rehearsal', 'draft', 'queued', 2, 2, account_id, None, None, owner, jid, requested_nonce)
    c.execute(COMPLETION, binds)
    return c.execute('SELECT * FROM jobs WHERE id=?', (cid,)).fetchone()


class NetworkTests(unittest.TestCase):
    def test_create_replay_and_capacity(self):
        c = fixture();self.addCleanup(c.close)
        check(create(c, 'custom') == 1, 'create')
        check(create(c, 'custom') == 0, 'creation replay is no-op')
        check(c.execute("SELECT agent_total FROM settings WHERE owner='own'").fetchone()[0] == 14, 'replay total unchanged')
        check(c.execute("SELECT child_count FROM agents WHERE owner='own' AND id='ambient'").fetchone()[0] == 3, 'replay parent count unchanged')
        c.execute("UPDATE settings SET agent_total=1000000 WHERE owner='own'")
        check(create(c, 'over-cap') == 0, 'cap guarded in insert')
        check(c.execute("SELECT child_count FROM agents WHERE owner='own' AND id='ambient'").fetchone()[0] == 3, 'rejected creation does not increment parent')

    def test_assignment_retirement_orderings(self):
        for first in ['route', 'retire']:
            c = fixture();self.addCleanup(c.close)
            create(c, 'custom')
            if first == 'route':
                check(route(c, 'custom') == 1, 'assignment accepted')
                check(lifecycle(c, 'custom') == 0, 'assignment first blocks retirement')
            else:
                check(lifecycle(c, 'custom') == 1, 'retirement accepted')
                check(route(c, 'custom') == 0, 'retirement first blocks assignment')

    def test_child_retirement_orderings(self):
        for first in ['child', 'retire']:
            c = fixture();self.addCleanup(c.close)
            create(c, 'parent')
            if first == 'child':
                check(create(c, 'child', 'parent') == 1, 'child inserted')
                check(lifecycle(c, 'parent') == 0, 'child first blocks retirement')
            else:
                check(lifecycle(c, 'parent') == 1, 'parent retired')
                check(create(c, 'child', 'parent') == 0, 'retirement first blocks child insertion')

    def test_restore_full_ancestry(self):
        c = fixture();self.addCleanup(c.close)
        create(c, 'parent')
        create(c, 'child', 'parent')
        check(lifecycle(c, 'child') == 1, 'child retired')
        check(lifecycle(c, 'parent') == 1, 'parent retired after child')
        check(lifecycle(c, 'child', False, 2) == 0, 'cannot restore below retired parent')
        check(lifecycle(c, 'parent', False, 2) == 1, 'restore parent under enabled chain')
        check(lifecycle(c, 'child', False, 2) == 0, 'restored paused parent still blocks child restore')
        c.execute("UPDATE agents SET paused=0 WHERE owner='own' AND id='parent'")
        c.execute("UPDATE agents SET paused=1 WHERE owner='own' AND id='astra'")
        check(lifecycle(c, 'child', False, 2) == 0, 'distant paused ancestor blocks restore')
        c.execute("UPDATE agents SET paused=0 WHERE owner='own' AND id='astra'")
        check(lifecycle(c, 'child', False, 2) == 1, 'full enabled chain allows restore')
        check(c.execute("SELECT paused FROM agents WHERE owner='own' AND id='child'").fetchone()[0] == 1, 'restored child stays paused')

    def test_completion_routing_precedence(self):
        c = fixture();self.addCleanup(c.close)
        create(c, 'studio')
        create(c, 'override')
        aid = account(c)
        check(complete_child(c)['agent'] == 'ambient-writer', 'implicit core fallback')
        check(route(c, 'studio') == 1, 'studio route accepted')
        check(complete_child(c, account_id=aid)['agent'] == 'studio', 'studio fallback for unrouted account')
        check(route(c, 'override', account=aid) == 1, 'account route accepted')
        check(complete_child(c, account_id=aid)['agent'] == 'override', 'account overrides studio')
        c.execute("UPDATE agents SET paused=1 WHERE owner='own' AND id='override'")
        check(complete_child(c, account_id=aid)['agent'] == 'override', 'paused override not silently rerouted')
        check(route(c, None, 1, account=aid) == 1, 'reset preserves account route row')
        check(complete_child(c, account_id=aid)['agent'] == 'studio', 'null account override falls through')
        check(route(c, 'override', 1, account=aid) == 0, 'stale revision cannot overwrite reset')
        check(route(c, None, 1) == 1, 'studio reset accepted')
        check(complete_child(c, account_id=aid)['agent'] == 'ambient-writer', 'both null routes use core')
        check(complete_child(c, requested_nonce='lost') is None, 'lost completion nonce creates no child')

    def test_completion_retirement_orderings(self):
        c = fixture();self.addCleanup(c.close)
        create(c, 'custom')
        route(c, 'custom')
        child = complete_child(c)
        route(c, None, 1)
        check(lifecycle(c, 'custom') == 0, 'existing delegated queued job prevents retirement after route reset')
        c.execute("UPDATE jobs SET status='cancelled' WHERE id=?", (child['id'],))
        check(lifecycle(c, 'custom') == 1, 'resolved jobs allow retirement')
        check(complete_child(c)['agent'] == 'ambient-writer', 'future completion uses reset route after retirement')

    def test_tenancy_and_eligibility(self):
        c = fixture();self.addCleanup(c.close)
        create(c, 'custom', owner='other')
        check(route(c, 'custom') == 0, 'foreign agent rejected')
        check(create(c, 'child', parent='custom') == 0, 'foreign parent rejected')
        check(lifecycle(c, 'custom') == 0, 'foreign retirement rejected')
        foreign = account(c, 'other')
        check(route(c, 'ambient-writer', account=foreign) == 0, 'foreign account rejected')
        check(route(c, 'gaming-writer') == 0, 'wrong lane rejected')
        check(route(c, 'ambient-editor') == 0, 'wrong role rejected')
        create(c, 'ownroute')
        route(c, 'ownroute')
        check(complete_child(c, owner='other')['agent'] == 'ambient-writer', 'foreign routes do not affect completion')

    def test_unfinished_work_retirement(self):
        for status in ['queued', 'running', 'blocked', 'failed', 'uncertain', 'succeeded', 'cancelled']:
            c = fixture();self.addCleanup(c.close)
            create(c, 'custom')
            route(c, 'custom')
            child = complete_child(c)
            route(c, None, 1)
            c.execute('UPDATE jobs SET status=? WHERE id=?', (status, child['id']))
            check(lifecycle(c, 'custom') == (1 if status in ['succeeded', 'cancelled'] else 0), 'retirement status ' + status)

    def test_atomic_creation_audit_rollback(self):
        c=fixture();self.addCleanup(c.close)
        c.executescript("CREATE TRIGGER fail_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'fixture failure'); END;")
        audit=next(s for s in strings if s.startswith('INSERT INTO events'))
        with self.assertRaises(sqlite3.IntegrityError):
            with c:
                c.execute(CREATE,('own','rollback','Rollback','writer','model',0,1,'instructions','writer','rollback','own','ambient'))
                c.execute(CHILD_COUNTER,('own','ambient'))
                c.execute(TOTAL_COUNTER,('own',))
                c.execute(audit,(str(uuid.uuid4()),'own','Created fixture',0))
        self.assertIsNone(c.execute("SELECT id FROM agents WHERE id='rollback'").fetchone())
        self.assertEqual(c.execute("SELECT agent_total FROM settings WHERE owner='own'").fetchone()[0],13)
        self.assertEqual(c.execute("SELECT child_count FROM agents WHERE owner='own' AND id='ambient'").fetchone()[0],2)

    def test_creation_replay_does_not_duplicate_audit(self):
        c=fixture();self.addCleanup(c.close);audit=next(s for s in strings if s.startswith('INSERT INTO events'))
        for _ in range(2):
            with c:
                c.execute(CREATE,('own','once','Once','writer','model',0,1,'instructions','writer','once','own','ambient'))
                c.execute(CHILD_COUNTER,('own','ambient'))
                c.execute(TOTAL_COUNTER,('own',))
                c.execute(audit,(str(uuid.uuid4()),'own','Created fixture',0))
        self.assertEqual(c.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)

    def test_deployed_core_backfill(self):
        c=sqlite3.connect(':memory:');self.addCleanup(c.close);migrations=sorted((root/'drizzle').glob('*.sql'))
        for p in migrations[:3]:c.executescript(p.read_text())
        c.execute("INSERT INTO settings(owner) VALUES('legacy')")
        for aid,parent in [('astra',None),('ambient','astra'),('ambient-writer','ambient'),('ambient-editor','ambient')]:
            c.execute('INSERT INTO agents(owner,id,parent,name,role,lane,model,instructions,color) VALUES(?,?,?,?,?,?,?,?,?)',('legacy',aid,parent,aid,'Legacy role','ambient','saved-model','saved instructions','#abc'))
        c.executescript(migrations[3].read_text())
        self.assertEqual(c.execute("SELECT task_role,depth,child_count,core,model,instructions FROM agents WHERE id='ambient'").fetchone(),('lead',1,2,1,'saved-model','saved instructions'))
        self.assertEqual(c.execute("SELECT task_role,depth FROM agents WHERE id='ambient-editor'").fetchone(),('editor',2))
        self.assertEqual(c.execute('SELECT agent_total FROM settings').fetchone()[0],4)

if __name__=='__main__':unittest.main()
