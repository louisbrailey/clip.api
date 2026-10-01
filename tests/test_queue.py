"""Exercise the actual claim SQL and committed migrations against SQLite.
No rewritten queue implementation is used in these tests.
"""
import re
import sqlite3
import time
from pathlib import Path
import unittest
ROOT=Path(__file__).parents[1]
STORE=(ROOT/'lib/store.ts').read_text()
CLAIM=re.search(r'return sql\(\s*`(UPDATE jobs SET status=.*?)`',STORE,re.S).group(1)

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.db.row_factory=sqlite3.Row
        for f in sorted((ROOT/'drizzle').glob('*.sql')):self.db.executescript(f.read_text())
        self.now=int(time.time()*1000);self.day=self.now//86400000
        for owner in ['alice','bob']:
            self.db.execute('INSERT INTO settings(owner) VALUES(?)',(owner,))
            self.db.execute('INSERT INTO workers(id,owner,name,key_hash,created) VALUES(?,?,?,?,?)',(owner+'-worker',owner,'Test worker',owner+'-hash',self.now))
            for id,parent in [('astra',None),('ambient','astra'),('ambient-writer','ambient'),('ambient-editor','ambient')]:
                self.db.execute('INSERT INTO agents(owner,id,parent,name,role,lane,model,instructions,color,core) VALUES(?,?,?,?,?,?,?,?,?,1)',(owner,id,parent,id,'writer','ambient','gpt-6-astra','original work','#fff'))
    def tearDown(self):self.db.close()
    def job(self,id,owner='alice',agent='ambient-writer',kind='draft',**kw):
        data={'id':id,'owner':owner,'agent':agent,'title':id,'brief':'Original work','lane':'ambient','mode':'live','kind':kind,'created':self.now,'scheduled':self.now,**kw}
        self.db.execute('INSERT INTO jobs('+','.join(data)+') VALUES('+','.join('?' for _ in data)+')',list(data.values()))
    def claim(self,key='key',owner='alice'):
        worker=owner+'-worker'
        return self.db.execute(CLAIM,(key,self.now+180000,worker,self.day,owner,key,worker,owner,'live',self.now,self.day,self.now,self.day)).fetchone()
    def test_claim_is_fenced_and_reserves_budget(self):
        self.job('one');j=self.claim();self.assertEqual(j['reserve'],20000);self.assertEqual(j['status'],'running');self.assertEqual(j['attempts'],1);self.assertEqual(j['lease'],'key')
    def test_claim_request_key_cannot_claim_twice(self):
        self.job('one');self.job('two');self.claim();self.assertIsNone(self.claim());self.assertEqual(self.db.execute("SELECT COUNT(*) FROM jobs WHERE status='running'").fetchone()[0],1)
    def test_cross_owner_claims_are_isolated(self):
        self.job('bobs',owner='bob');self.assertIsNone(self.claim());self.assertEqual(self.claim(owner='bob')['id'],'bobs')
    def test_global_pause(self):
        self.job('one');self.db.execute("UPDATE settings SET paused=1 WHERE owner='alice'");self.assertIsNone(self.claim())
    def test_ancestor_pause(self):
        self.job('one');self.db.execute("UPDATE agents SET paused=1 WHERE id='astra'");self.assertIsNone(self.claim())
    def test_global_concurrency_limit(self):
        self.db.execute("UPDATE settings SET concurrency=1 WHERE owner='alice'");self.job('one');self.job('two',agent='ambient-editor');self.claim();self.assertIsNone(self.claim('second'))
    def test_worker_concurrency_limit_and_independence(self):
        self.db.execute("UPDATE workers SET concurrency=1 WHERE id='alice-worker'")
        self.db.execute("INSERT INTO workers(id,owner,name,key_hash,concurrency,created) VALUES('alice-worker-2','alice','Second','second-hash',1,?)",(self.now,))
        self.job('one');self.job('two',agent='ambient-editor')
        self.assertIsNotNone(self.claim())
        self.assertIsNone(self.claim('second'))
        args=('third',self.now+180000,'alice-worker-2',self.day,'alice','third','alice-worker-2','alice','live',self.now,self.day,self.now,self.day)
        self.assertEqual(self.db.execute(CLAIM,args).fetchone()['worker_id'],'alice-worker-2')
    def test_paused_worker_cannot_claim(self):
        self.db.execute("UPDATE workers SET paused=1 WHERE id='alice-worker'");self.job('one');self.assertIsNone(self.claim())
    def test_agent_concurrency_limit(self):
        self.db.execute("UPDATE agents SET concurrency=1 WHERE id='ambient-writer'");self.job('one');self.job('two');self.claim();self.assertIsNone(self.claim('second'))
    def test_budget_reservation_prevents_overcommit(self):
        self.db.execute("UPDATE settings SET daily_tokens=20000 WHERE owner='alice'");self.job('one');self.job('two');self.claim();self.assertIsNone(self.claim('second'))
    def test_daily_ledger_blocks_spend(self):
        self.job('one');self.db.execute('INSERT INTO usage VALUES(?,?,?,?)',('charge','alice',self.day,90000));self.assertIsNone(self.claim())
    def test_prior_day_usage_does_not_block_today(self):
        self.job('one');self.db.execute('INSERT INTO usage VALUES(?,?,?,?)',('charge','alice',self.day-1,100000));self.assertIsNotNone(self.claim())
    def test_future_schedule_not_claimed(self):
        self.job('future',scheduled=self.now+10000);self.assertIsNone(self.claim())
    def test_dependency_must_succeed(self):
        self.job('parent',status='failed');self.job('child',depends='parent');self.assertIsNone(self.claim());self.db.execute("UPDATE jobs SET status='succeeded' WHERE id='parent'");self.assertEqual(self.claim()['id'],'child')
    def test_retry_limit(self):
        self.job('one',attempts=3);self.assertIsNone(self.claim())
    def test_unapproved_upload_cannot_run(self):
        self.job('upload',kind='publish');self.assertIsNone(self.claim())
    def test_duplicate_publication_is_database_enforced(self):
        self.job('first',kind='publish',asset='asset-one')
        with self.assertRaises(sqlite3.IntegrityError):self.job('second',kind='publish',asset='asset-one')
    def test_uncertain_upload_keeps_deduplication_lock(self):
        self.job('first',kind='publish',asset='asset-one',status='uncertain')
        with self.assertRaises(sqlite3.IntegrityError):self.job('second',kind='publish',asset='asset-one')
    def test_expiry_accounting_uses_one_cutoff(self):
        self.job('expiring',status='running',reserve=20000,lease_until=1001,attempts=1,billed_day=self.day)
        insert=re.search(r'sql\(\s*"(INSERT OR IGNORE INTO usage\(id,\s*owner,day,tokens\) SELECT.*?)",\s*owner,\s*cutoff\s*,?\s*\)',STORE).group(1)
        update=re.search(r'sql\(\s*"(UPDATE jobs SET status=CASE WHEN kind=.*?)",\s*cutoff\s*\+\s*30000,\s*owner,\s*cutoff\s*,?\s*\)',STORE).group(1)
        for cutoff in [1000,1002]:
            with self.db:
                self.db.execute(insert,('alice',cutoff))
                self.db.execute(update,(cutoff+30000,'alice',cutoff))
            ledger=self.db.execute("SELECT COALESCE(SUM(tokens),0) FROM usage").fetchone()[0]
            reserve=self.db.execute("SELECT reserve FROM jobs WHERE id='expiring'").fetchone()[0]
            self.assertEqual(ledger+reserve,20000)
    def test_asset_pagination_and_account_picker(self):
        for i in range(70):
            self.db.execute('INSERT INTO assets(id,owner,name,object_key,mime,size,rights,evidence,created) VALUES(?,?,?,?,?,?,?,?,?)',(str(i),'alice','media-'+str(i),str(i),'video/mp4',100,'original','Original generated work',i))
        query=re.search(r'sql\(\s*"(SELECT \* FROM assets WHERE owner=.*?LIMIT 60 OFFSET \?)",\s*owner,\s*search,\s*offset',STORE).group(1)
        rows=self.db.execute(query,('alice','',60)).fetchall();self.assertEqual(len(rows),10)
        self.assertEqual(self.db.execute(query,('alice','media-0',0)).fetchone()['id'],'0')
    def test_agent_status_includes_older_running_jobs(self):
        self.job('old',status='running',created=1)
        for i in range(70):self.job('new'+str(i),created=i+2)
        query=re.search(r'sql\(\s*"(SELECT agent,status,COUNT\(\*\) AS n FROM jobs WHERE owner=.*?GROUP BY agent,status)",\s*owner',STORE).group(1)
        rows=self.db.execute(query,('alice',)).fetchall()
        self.assertEqual(next(row['n'] for row in rows if row['status']=='running'),1)
    def test_render_uses_no_model_budget(self):
        self.db.execute("INSERT INTO usage VALUES('spent','alice',?,100000)",(self.day,))
        self.job('render',kind='render',approved=1,render_spec='{}')
        result=self.claim();self.assertEqual(result['kind'],'render');self.assertEqual(result['reserve'],0)
    def test_unapproved_render_cannot_be_claimed(self):
        self.job('render',kind='render',render_spec='{}');self.assertIsNone(self.claim())
    def test_render_output_binding_is_unique(self):
        values=('asset-one','alice','video','object-one','video/mp4',100,'original','Generated locally',self.now,'render-job')
        statement='INSERT INTO assets(id,owner,name,object_key,mime,size,rights,evidence,created,source_job) VALUES(?,?,?,?,?,?,?,?,?,?)'
        self.db.execute(statement,values)
        with self.assertRaises(sqlite3.IntegrityError):self.db.execute(statement,('asset-two',)+values[1:])
    def test_ten_thousand_account_registry(self):
        self.db.executemany('INSERT INTO accounts(id,owner,platform,handle,lane,external_id,credential_ref,authorized,created) VALUES(?,?,?,?,?,?,?,?,?)',((str(i),'alice','youtube','@account'+str(i),'ambient','external'+str(i),'YT_REFERENCE',1,self.now) for i in range(10000)))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM accounts WHERE owner='alice'").fetchone()[0],10000)
        rows=self.db.execute("SELECT id FROM accounts WHERE owner='alice' ORDER BY created DESC LIMIT 60 OFFSET 9960").fetchall();self.assertEqual(len(rows),40)
if __name__=='__main__':unittest.main()
