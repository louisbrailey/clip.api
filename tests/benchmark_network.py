"""Reproducible local SQLite registry benchmark; no provider calls or production writes.
Default: one million lightweight agent definitions, removed after measurement.
This does not establish D1 service capacity, concurrent models or end-to-end latency.
"""
import argparse
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'lib/network.ts').read_text()
NODE=re.search(r'nodeSelect\s*=\s*`(.*?)`',SOURCE,re.S).group(1)
def query_in(function):
    section=SOURCE.split('export async function '+function+'(',1)[1]
    return re.search(r'sql\(\s*`(.*?)`',section,re.S).group(1).replace('${nodeSelect}',NODE)
SEARCH=query_in('searchAgents').replace('${boundary}','AND a.search_name<?')
CHILD=next(q.replace('${nodeSelect}',NODE) for q in re.findall(r'sql\(\s*`(.*?)`',SOURCE,re.S) if 'a.parent=?' in q)

def measure(c,label,query,binds):
    ticks=0
    def tick():
        nonlocal ticks
        ticks+=1
    c.set_progress_handler(tick,100)
    started=time.perf_counter();rows=c.execute(query,binds).fetchall();elapsed=time.perf_counter()-started
    c.set_progress_handler(None,0)
    plan=[r[3] for r in c.execute('EXPLAIN QUERY PLAN '+query,binds)]
    result=dict(label=label,rows=len(rows),elapsed_ms=round(elapsed*1000,3),approximate_vm_steps=ticks*100,json_bytes=len(json.dumps([dict(r) for r in rows]).encode()),query_plan=plan)
    assert ticks*100<10000,(label,'unbounded page traversal',ticks)
    return result

def run(rows):
    with tempfile.TemporaryDirectory(prefix='constellation-registry-') as directory:
        path=Path(directory)/'fixture.sqlite';c=sqlite3.connect(path);c.row_factory=sqlite3.Row
        for p in sorted((ROOT/'drizzle').glob('*.sql')):c.executescript(p.read_text())
        c.execute('INSERT INTO settings(owner,agent_total) VALUES(?,?)',('benchmark',rows))
        started=time.perf_counter()
        # Distinct and repeated names exercise composite keyset seeking.
        c.executemany('INSERT INTO agents(owner,id,parent,name,role,lane,model,instructions,color,task_role,depth,search_name) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
          (('benchmark',f'agent-{i:07d}','ambient',f'Worker {i:07d}' if i%2==0 else 'Shared writer','writer','ambient','fixture-model','Original fixture instructions','#abc','writer',2,f'worker {i:07d}' if i%2==0 else 'shared writer') for i in range(rows)))
        c.commit();c.execute('PRAGMA optimize')
        seed_seconds=round(time.perf_counter()-started,3)
        # Include a large unrelated range after narrow and absent prefixes.
        scenarios=[('first prefix page','worker','', 'workes'),
                   ('late unique page',f'worker {rows-100:07d}',f'agent-{rows-100:07d}','workes'),
                   ('late repeated-name page','shared writer',f'agent-{rows-100:07d}','shares'),
                   ('narrow prefix final page','worker 0000990','agent-0000990','worker 0001'),
                   ('missing prefix','shared x','','shared y')]
        measurements=[measure(c,label,SEARCH,('benchmark',name,aid,upper)) for label,name,aid,upper in scenarios]
        measurements.append(measure(c,'late child page',CHILD,('benchmark','ambient',f'agent-{rows-100:07d}')))
        assert [r['rows'] for r in measurements]==[21,21,21,4,0,13]
        total=c.execute('SELECT COUNT(*) FROM agents').fetchone()[0]
        result=dict(scope='Local SQLite fixture only; not live D1 or concurrent model execution',agent_definitions=total,seed_seconds=seed_seconds,database_bytes=path.stat().st_size,sqlite_version=sqlite3.sqlite_version,measurements=measurements)
        c.close();return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--rows',type=int,default=1000000);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.rows<10000 or args.rows>1000000:parser.error('--rows must be between 10000 and 1000000')
    result=run(args.rows)
    if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
