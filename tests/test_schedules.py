"""Run the application's recurrence and claim SQL against committed migrations."""
import concurrent.futures
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import unittest
import uuid

ROOT=Path(__file__).parents[1]
SCHEDULES=(ROOT/'lib/schedules.ts').read_text()
STORE=(ROOT/'lib/store.ts').read_text()
API=(ROOT/'app/api/control/route.ts').read_text()
DUE=re.search(r'dueSchedules\s*=\s*`(.*?)`',SCHEDULES,re.S).group(1)
INSERT=re.search(r'sql\(\s*`(INSERT OR IGNORE INTO jobs.*?)`',SCHEDULES,re.S).group(1).replace('${dueSchedules}',DUE)
ADVANCE=re.search(r'sql\(\s*`(UPDATE schedules SET.*?)`',SCHEDULES,re.S).group(1)
EVENT=re.search(r'sql\(\s*`(INSERT OR IGNORE INTO events.*?)`',SCHEDULES,re.S).group(1)
CLAIM=re.search(r'return sql\(\s*`(UPDATE jobs SET status=.*?)`',STORE,re.S).group(1)
CHILD=re.search(r'sql\(\s*"(INSERT OR IGNORE INTO jobs.*?)"',API,re.S).group(1)
DISCARD=re.search(r"sql\(\s*`(UPDATE jobs SET status='cancelled'.*?)`",API,re.S).group(1)

CREATE=re.search(r'sql\(\s*`(INSERT OR IGNORE INTO schedules.*?)`',API,re.S).group(1)
EDIT=re.search(r'sql\(\s*`(UPDATE schedules SET title=.*?)`',API,re.S).group(1)
CONTROL_EVENT=re.search(r'sql\(\s*"(INSERT INTO events.*?WHERE changes\(\)>0)"',API,re.S).group(1)

class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        self.now=1800000000000;self.day=self.now//86400000
        for f in sorted((ROOT/'drizzle').glob('*.sql')):self.db.executescript(f.read_text())
        for owner in ('alice','bob'):
            self.db.execute('INSERT INTO settings(owner) VALUES(?)',(owner,))
            for agent,parent in [('astra',None),('ambient','astra'),('ambient-writer','ambient'),('ambient-editor','ambient')]:
                self.db.execute('INSERT INTO agents(owner,id,parent,name,role,lane,model,instructions,color) VALUES(?,?,?,?,?,?,?,?,?)',(owner,agent,parent,agent,'writer','ambient','gpt-6-astra','original work','#fff'))
            self.db.execute('INSERT INTO accounts(id,owner,platform,handle,lane,external_id,credential_ref,authorized,created) VALUES(?,?,?,?,?,?,?,?,?)',(owner+'-account',owner,'youtube','@'+owner,'ambient',owner+'-channel','YT_REFERENCE',1,self.now))
        self.db.commit()
    def tearDown(self):self.db.close()
    def schedule(self,id='recurring',owner='alice',**kw):
        values=dict(id=id,owner=owner,account=owner+'-account',title='Original meditation',brief='Create an original calming script.',mode='live',interval_minutes=60,next_run=self.now,created=self.now,updated=self.now,**kw)
        self.db.execute('INSERT INTO schedules('+','.join(values)+') VALUES('+','.join('?' for _ in values)+')',list(values.values()));self.db.commit()
    def due(self,owner='alice',mode='live'):
        return [r[0] for r in self.db.execute(DUE,(owner,mode,self.now))]
    def expand(self,schedule='recurring',job=None,owner='alice',mode='live',db=None,seed=123):
        db=db or self.db;job=job or str(uuid.uuid4())
        with db:
            db.execute(INSERT,(job,self.now,self.now,seed,owner,schedule,owner,mode,self.now))
            db.execute(ADVANCE,(self.now,self.now,owner,schedule,job))
            db.execute(EVENT,(job,self.now,owner,job))
        return job
    def row(self,id='recurring'):return self.db.execute('SELECT * FROM schedules WHERE id=?',(id,)).fetchone()
    def claim(self):
        return self.db.execute(CLAIM,('lease',self.now+180000,self.day,'alice','lease','alice','live',self.now,self.day,self.now,self.day)).fetchone()
    def control(self,query,args):
        with self.db:
            result=self.db.execute(query,args).rowcount
            self.db.execute(CONTROL_EVENT,(str(uuid.uuid4()),'alice','Fixture schedule control',self.now))
        return result
    def create_args(self):
        return ('recurring','alice','alice-account','Original meditation','Create an original calming script.','live',60,self.now,None,0,self.now,self.now,'workflow',None,0,'fixture-creation-hash','alice','alice-account','workflow','alice')
    def test_creation_replay_has_one_schedule_and_audit_event(self):
        self.assertEqual(self.control(CREATE,self.create_args()),1)
        self.assertEqual(self.control(CREATE,self.create_args()),0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM schedules').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)
    def test_audit_failure_rolls_back_schedule_control(self):
        self.db.executescript("CREATE TRIGGER fail_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'test failure'); END;")
        with self.assertRaises(sqlite3.IntegrityError):self.control(CREATE,self.create_args())
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM schedules').fetchone()[0],0)
    def test_edit_cannot_reuse_historical_occurrence_or_emit_false_audit(self):
        self.schedule();self.expand();before=self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        args=('New title','New original brief','live',60,self.now,None,0,self.now,None,0,'alice','recurring','alice-account',self.row()['revision'],'workflow',self.now)
        self.assertEqual(self.control(EDIT,args),0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],before)
        self.assertEqual(self.row()['title'],'Original meditation')
    def test_one_occurrence_and_lost_response_replay(self):
        self.schedule();self.expand(job='first');self.expand(job='first');self.expand(job='retry')
        self.assertEqual(self.row()['generated_count'],1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],1)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)
    def test_coalesce_missed_intervals_preserves_cadence(self):
        self.schedule();nominal=self.now-5*3600000-900000
        self.db.execute('UPDATE schedules SET next_run=?',(nominal,));self.db.commit();self.expand()
        self.assertEqual(self.row()['next_run'],self.now+2700000)
        self.assertEqual(self.db.execute('SELECT occurrence FROM jobs').fetchone()[0],nominal)
        self.assertEqual(self.row()['generated_count'],1)
    def test_all_generation_guards_rechecked_after_candidate_read(self):
        self.schedule();self.assertEqual(self.due(),['recurring'])
        for query in ["UPDATE schedules SET paused=1", "UPDATE settings SET paused=1", "UPDATE accounts SET paused=1", "UPDATE accounts SET authorized=0", "UPDATE agents SET paused=1 WHERE id='astra'", "UPDATE agents SET paused=1 WHERE id='ambient'", "UPDATE schedules SET max_runs=1,generated_count=1", "UPDATE schedules SET mode='rehearsal'", "UPDATE schedules SET next_run=next_run+1"]:
            with self.subTest(query=query):
                self.db.execute('SAVEPOINT guard');self.db.execute(query)
                before=self.row()['generated_count']
                self.db.execute(INSERT,('blocked',self.now,self.now,123,'alice','recurring','alice','live',self.now))
                self.db.execute(ADVANCE,(self.now,self.now,'alice','recurring','blocked'))
                self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)
                self.assertEqual(self.row()['generated_count'],before)
                self.db.execute('ROLLBACK TO guard');self.db.execute('RELEASE guard')
    def test_owner_and_mode_are_isolated(self):
        self.schedule(owner='bob');self.expand();self.assertEqual(self.row()['generated_count'],0)
        self.assertEqual(self.due(),[]);self.assertEqual(self.due('bob','rehearsal'),[])
        self.expand(owner='bob');self.assertEqual(self.row()['generated_count'],1)
    def test_missing_or_foreign_account_fails_closed(self):
        self.schedule();self.db.execute("UPDATE schedules SET account='bob-account'");self.db.commit()
        self.assertEqual(self.due(),[]);self.expand();self.assertEqual(self.row()['generated_count'],0)
    def test_blocked_candidates_do_not_starve_later_work(self):
        for i in range(25):self.schedule('paused-'+str(i),paused=1)
        for i in range(15):self.schedule('ready-'+str(i))
        self.assertEqual(len(self.due()),10);self.assertTrue(all(i.startswith('ready-') for i in self.due()))
    def test_entire_occurrence_holds_future_runs_until_resolved(self):
        self.schedule();id=self.expand()
        self.db.execute("UPDATE jobs SET parent='prior-root'")
        self.db.execute('UPDATE schedules SET next_run=?',(self.now,));self.db.commit()
        for status in ['queued','running','blocked','failed','uncertain']:
            self.db.execute('UPDATE jobs SET status=?',(status,));self.db.commit()
            self.assertEqual(self.due(),[],status)
        for status in ['cancelled','succeeded']:
            self.db.execute('UPDATE jobs SET status=?',(status,));self.db.commit()
            self.assertEqual(self.due(),['recurring'],status)
    def test_account_and_studio_and_schedule_pause_hold_root_claim(self):
        self.schedule();self.expand()
        for query in ["UPDATE accounts SET paused=1", "UPDATE agents SET paused=1 WHERE id='ambient'", "UPDATE schedules SET paused=1"]:
            with self.subTest(query=query):
                self.db.execute('SAVEPOINT hold');self.db.execute(query);self.assertIsNone(self.claim())
                self.db.execute('ROLLBACK TO hold');self.db.execute('RELEASE hold')
        self.assertEqual(self.claim()['agent'],'astra')
    def test_descendants_inherit_account_and_occurrence_without_publish_approval(self):
        self.schedule();id=self.expand()
        self.db.execute("UPDATE jobs SET status='succeeded',completion_nonce='winner'")
        for i in range(2):
            self.db.execute(CHILD,(f'child-{i}','alice',id,None,'alice','account:alice-account','writer','alice','studio:ambient','writer','ambient-writer','Original script','Original content','ambient','live','draft','queued',self.now,self.now,'alice-account','recurring',self.now,'alice',id,'winner'))
        rows=self.db.execute("SELECT * FROM jobs WHERE parent=?",(id,)).fetchall()
        self.assertEqual(len(rows),2);self.assertTrue(all(r['account']=='alice-account' and r['schedule_id']=='recurring' and r['occurrence']==self.now and r['approved']==0 for r in rows))
        self.db.execute("UPDATE schedules SET paused=1");self.assertIsNone(self.claim())
    def test_losing_completion_cannot_create_children(self):
        self.schedule();id=self.expand();self.db.execute("UPDATE jobs SET status='succeeded',completion_nonce='winner'")
        self.db.execute(CHILD,('child','alice',id,None,'alice','account:alice-account','writer','alice','studio:ambient','writer','ambient-writer','Original script','Original content','ambient','live','draft','queued',self.now,self.now,'alice-account','recurring',self.now,'alice',id,'loser'))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs WHERE parent IS NOT NULL").fetchone()[0],0)
    def test_edit_only_changes_future_snapshot(self):
        self.schedule();self.expand();self.db.execute("UPDATE schedules SET brief='A revised original production brief',mode='rehearsal'")
        job=self.db.execute('SELECT * FROM jobs').fetchone()
        self.assertEqual(job['brief'],'Create an original calming script.');self.assertEqual(job['mode'],'live')
    def test_run_limit_stops_after_last_occurrence(self):
        self.schedule(max_runs=1);self.expand();self.db.execute("UPDATE jobs SET status='succeeded'")
        self.db.execute('UPDATE schedules SET next_run=?',(self.now,));self.db.commit()
        self.assertEqual(self.due(),[]);self.expand();self.assertEqual(self.row()['generated_count'],1)
    def test_discard_cannot_race_running_call_and_is_occurrence_scoped(self):
        self.schedule();self.expand();self.db.execute("UPDATE jobs SET status='running'")
        self.assertEqual(self.db.execute(DISCARD,('alice','recurring',self.now)).rowcount,0)
        self.db.execute("UPDATE jobs SET status='queued'")
        self.assertEqual(self.db.execute(DISCARD,('bob','recurring',self.now)).rowcount,0)
        self.assertEqual(self.db.execute(DISCARD,('alice','recurring',self.now-1)).rowcount,0)
        self.assertEqual(self.db.execute(DISCARD,('alice','recurring',self.now)).rowcount,1)
        self.assertEqual(self.row()['paused'],0)
    def test_update_failure_rolls_back_job_and_event(self):
        self.schedule();self.db.executescript("CREATE TRIGGER fail_advance BEFORE UPDATE ON schedules BEGIN SELECT RAISE(ABORT,'test failure'); END;")
        with self.assertRaises(sqlite3.IntegrityError):self.expand()
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)
        self.assertEqual(self.row()['generated_count'],0)
    def ambient(self,**kw):
        kw.setdefault('render_recipe',json.dumps({'seconds':10,'noise':'pink','theme':'ocean'}));self.schedule(production_kind='ambient',render_approved=1,**kw)
    def test_ambient_occurrence_snapshots_recipe_seed_and_account(self):
        self.ambient();self.expand(seed=123)
        j=self.db.execute('SELECT * FROM jobs').fetchone()
        self.assertEqual((j['agent'],j['kind'],j['approved'],j['account']),('ambient-editor','render',1,'alice-account'))
        self.assertEqual(json.loads(j['render_spec']),{'seconds':10,'noise':'pink','theme':'ocean','seed':123})
        self.assertEqual(self.claim()['reserve'],0)
    def test_ambient_float_bound_seed_is_serialized_as_json_integer(self):
        self.ambient();self.expand(seed=595646801.0)
        seed=json.loads(self.db.execute('SELECT render_spec FROM jobs').fetchone()[0])['seed']
        self.assertIs(type(seed),int);self.assertEqual(seed,595646801)
    def test_ambient_seed_upper_boundary_stays_json_integer(self):
        self.ambient();self.expand(seed=2147483647)
        seed=json.loads(self.db.execute('SELECT render_spec FROM jobs').fetchone()[0])['seed']
        self.assertIs(type(seed),int);self.assertEqual(seed,2147483647)
    def test_ambient_replay_does_not_replace_seed_or_count(self):
        self.ambient();self.expand(job='first',seed=123);self.expand(job='first',seed=456);self.expand(job='second',seed=789)
        self.assertEqual(self.row()['generated_count'],1)
        self.assertEqual(json.loads(self.db.execute('SELECT render_spec FROM jobs').fetchone()[0])['seed'],123)
    def test_ambient_recipe_edit_only_affects_later_occurrences(self):
        self.ambient();self.expand(job='first',seed=123)
        self.db.execute("UPDATE schedules SET render_recipe=?,next_run=?",(json.dumps({'seconds':20,'noise':'brown','theme':'forest'}),self.now+1));self.db.execute("UPDATE jobs SET status='succeeded'");self.db.commit()
        self.now+=1;self.expand(job='second',seed=456)
        recipes={row[0]:json.loads(row[1]) for row in self.db.execute('SELECT id,render_spec FROM jobs')}
        self.assertEqual(recipes['first']['seconds'],10);self.assertEqual(recipes['second'],{'seconds':20,'noise':'brown','theme':'forest','seed':456})
    def test_ambient_narration_script_snapshots_per_occurrence(self):
        self.ambient(render_recipe=json.dumps({'seconds':10,'noise':'pink','theme':'ocean','script':'Original narration'}));self.expand(job='first',seed=123)
        self.db.execute("UPDATE schedules SET render_recipe=?,next_run=?",(json.dumps({'seconds':10,'noise':'pink','theme':'ocean','script':'Revised narration'}),self.now+1));self.db.execute("UPDATE jobs SET status='succeeded'");self.db.commit()
        self.now+=1;self.expand(job='second',seed=456)
        scripts={row[0]:json.loads(row[1])['script'] for row in self.db.execute('SELECT id,render_spec FROM jobs')}
        self.assertEqual(scripts,{'first':'Original narration','second':'Revised narration'})
    def test_ambient_guards_rechecked_inside_expansion(self):
        self.ambient()
        for query in ["UPDATE schedules SET render_approved=0","UPDATE schedules SET render_recipe=NULL","UPDATE schedules SET mode='rehearsal'","UPDATE accounts SET lane='sports'","UPDATE agents SET paused=1 WHERE id='ambient-editor'","UPDATE agents SET archived=1 WHERE id='ambient-editor'"]:
            with self.subTest(query=query):
                self.db.execute('SAVEPOINT ambient_guard');self.db.execute(query)
                self.db.execute(INSERT,('blocked',self.now,self.now,123,'alice','recurring','alice','live',self.now))
                self.assertEqual(self.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],0)
                self.db.execute('ROLLBACK TO ambient_guard');self.db.execute('RELEASE ambient_guard')
    def test_paused_renderer_does_not_starve_ready_model_schedule(self):
        self.ambient();self.db.execute("UPDATE agents SET paused=1 WHERE id='ambient-editor'");self.db.commit();self.schedule('model')
        self.assertEqual(self.due(),['model'])
    def test_scheduled_render_preflight_respects_schedule_pause_and_lease(self):
        self.ambient();self.expand();j=self.claim()
        query=re.search(r'renderEligibility = `(.*?)`',(ROOT/'lib/render.ts').read_text(),re.S).group(1)
        self.assertIsNotNone(self.db.execute(query,('alice',j['id'],'lease',self.now)).fetchone())
        self.db.execute('UPDATE schedules SET paused=1')
        self.assertIsNone(self.db.execute(query,('alice',j['id'],'lease',self.now)).fetchone())
        self.db.execute('UPDATE schedules SET paused=0')
        self.assertIsNone(self.db.execute(query,('alice',j['id'],'old-lease',self.now)).fetchone())
        self.assertIsNone(self.db.execute(query,('bob',j['id'],'lease',self.now)).fetchone())
    def test_schedule_output_kind_cannot_be_changed_by_edit(self):
        self.ambient();args=('New title','New original brief','live',60,self.now+1,None,0,self.now,None,0,'alice','recurring','alice-account',self.row()['revision'],'workflow',self.now+1)
        self.assertEqual(self.control(EDIT,args),0);self.assertEqual(self.row()['production_kind'],'ambient')
    def test_legacy_schedule_migration_preserves_configuration(self):
        db=sqlite3.connect(':memory:')
        try:
            files=sorted((ROOT/'drizzle').glob('*.sql'))
            for f in files[:-1]:db.executescript(f.read_text())
            db.execute("INSERT INTO schedules(id,owner,account,title,brief,mode,interval_minutes,next_run,created,updated) VALUES('legacy','alice','account','Title','Original brief','rehearsal',1440,123,1,1)")
            db.executescript(files[-1].read_text())
            self.assertEqual(db.execute("SELECT production_kind,render_recipe,render_approved,creation_hash,mode,interval_minutes,next_run FROM schedules").fetchone(),('workflow',None,0,None,'rehearsal',1440,123))
        finally:db.close()
    def test_competing_expanders_create_one_root_and_persist_after_restart(self):
        self.schedule()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'queue.sqlite';target=sqlite3.connect(path);self.db.backup(target);target.close()
            barrier=threading.Barrier(2)
            def attempt(_):
                db=sqlite3.connect(path,timeout=10)
                try:
                    candidate=db.execute(DUE,('alice','live',self.now)).fetchone()[0]
                    barrier.wait(timeout=10)
                    self.expand(schedule=candidate,db=db)
                finally:db.close()
            with concurrent.futures.ThreadPoolExecutor(2) as pool:list(pool.map(attempt,range(2)))
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT generated_count FROM schedules').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)

if __name__=='__main__':unittest.main()
