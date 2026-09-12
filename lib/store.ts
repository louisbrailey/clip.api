import { env } from "cloudflare:workers";
import { initialAgents, type Agent, type Job, type State } from "./domain";
export const now = () => Date.now();
export const day = () => Math.floor(now() / 86400000);
export function db() {
  if (!env.DB) throw new Error("Database unavailable");
  return env.DB;
}
export function bucket() {
  if (!env.BUCKET) throw new Error("Media storage unavailable");
  return env.BUCKET;
}
export const sql = (query: string, ...args: (string | number | null)[]) =>
  db()
    .prepare(query)
    .bind(...args);
export async function initialize(owner: string) {
  const existing = await sql(
    "SELECT owner FROM settings WHERE owner=?",
    owner,
  ).first();
  if (existing) return;
  await db().batch([
    sql("INSERT OR IGNORE INTO settings(owner) VALUES(?)", owner),
    ...initialAgents.map((a) =>
      sql(
        "INSERT OR IGNORE INTO agents(owner,id,parent,name,role,lane,model,paused,concurrency,instructions,color) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        owner,
        a.id,
        a.parent,
        a.name,
        a.role,
        a.lane,
        a.model,
        a.paused,
        a.concurrency,
        a.instructions,
        a.color,
      ),
    ),
  ]);
}
export function event(
  owner: string,
  type: string,
  message: string,
  job: string | null = null,
) {
  return sql(
    "INSERT INTO events(id,owner,type,message,job,created) VALUES(?,?,?,?,?,?)",
    crypto.randomUUID(),
    owner,
    type,
    message,
    job,
    now(),
  );
}
export async function state(
  owner: string,
  offset = 0,
  search = "",
): Promise<State> {
  const r = await db().batch<Record<string, unknown>>([
    sql("SELECT * FROM agents WHERE owner=? ORDER BY rowid", owner),
    sql(
      "SELECT * FROM jobs WHERE owner=? AND (instr(lower(title),lower(?))>0 OR instr(id,?)>0) ORDER BY created DESC, id DESC LIMIT 60 OFFSET ?",
      owner,
      search,
      search,
      offset,
    ),
    sql(
      "SELECT * FROM accounts WHERE owner=? AND (instr(lower(handle),lower(?))>0 OR instr(external_id,?)>0) ORDER BY created DESC LIMIT 60 OFFSET ?",
      owner,
      search,
      search,
      offset,
    ),
    sql(
      "SELECT * FROM assets WHERE owner=? AND instr(lower(name),lower(?))>0 ORDER BY created DESC LIMIT 60 OFFSET ?",
      owner,
      search,
      offset,
    ),
    sql(
      "SELECT * FROM events WHERE owner=? ORDER BY created DESC LIMIT 100",
      owner,
    ),
    sql(
      "SELECT paused,concurrency,daily_tokens,worker_seen,worker_hash IS NOT NULL AS has_worker_key FROM settings WHERE owner=?",
      owner,
    ),
    sql(
      "SELECT status,COUNT(*) AS n FROM jobs WHERE owner=? GROUP BY status",
      owner,
    ),
    sql(
      "SELECT (SELECT COALESCE(SUM(tokens),0) FROM usage WHERE owner=? AND day=?) AS tokens,(SELECT COALESCE(SUM(reserve),0) FROM jobs WHERE owner=?) AS reserved",
      owner,
      day(),
      owner,
    ),
    sql("SELECT COUNT(*) AS n FROM accounts WHERE owner=?", owner),
    sql("SELECT COUNT(*) AS n FROM assets WHERE owner=?", owner),
    sql(
      "SELECT agent,status,COUNT(*) AS n FROM jobs WHERE owner=? GROUP BY agent,status",
      owner,
    ),
    sql(
      "SELECT lane,status,COUNT(*) AS n FROM jobs WHERE owner=? GROUP BY lane,status",
      owner,
    ),
  ]);
  const counts: Record<string, number> = {};
  for (const v of r[6].results) counts[v.status as string] = v.n as number;
  // Lease tokens and storage keys never go to the browser.
  const visibleJobs = r[1].results.map(({ lease, owner: _owner, ...j }) => ({
    ...j,
    lease: null,
  }));
  const visibleAssets = r[3].results.map(
    ({ object_key, owner: _owner, ...a }) => ({ ...a, object_key: "" }),
  );
  const agentCounts: Record<string, Record<string, number>> = {},
    laneCounts: Record<string, Record<string, number>> = {};
  for (const row of r[10].results) {
    const id = String(row.agent);
    agentCounts[id] ??= {};
    agentCounts[id][String(row.status)] = Number(row.n);
  }
  for (const row of r[11].results) {
    const id = String(row.lane);
    laneCounts[id] ??= {};
    laneCounts[id][String(row.status)] = Number(row.n);
  }
  return {
    agent_counts: agentCounts,
    lane_counts: laneCounts,
    agents: r[0].results,
    jobs: visibleJobs,
    accounts: r[2].results,
    assets: visibleAssets,
    events: r[4].results,
    settings: r[5].results[0],
    counts,
    tokens_today: r[7].results[0].tokens,
    reserved_today: r[7].results[0].reserved,
    job_total: Object.values(counts).reduce((a, b) => a + b, 0),
    account_total: r[8].results[0].n,
    asset_total: r[9].results[0].n,
    now: now(),
  } as unknown as State;
}
export function newJob(
  owner: string,
  j: Partial<Job> & {
    id: string;
    agent: string;
    title: string;
    brief: string;
    lane: string;
    mode: string;
    kind: string;
  },
) {
  return sql(
    "INSERT INTO jobs(id,owner,parent,depends,agent,title,brief,lane,mode,kind,status,created,scheduled,account,asset,approved) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    j.id,
    owner,
    j.parent ?? null,
    j.depends ?? null,
    j.agent,
    j.title,
    j.brief,
    j.lane,
    j.mode,
    j.kind,
    j.status ?? "queued",
    now(),
    j.scheduled ?? now(),
    j.account ?? null,
    j.asset ?? null,
    j.approved ?? 0,
  );
}
export async function sweep(owner: string) {
  const cutoff = now();
  // Unknown model charges retain the full reservation. Publishing is never replayed.
  await db().batch([
    sql(
      "INSERT OR IGNORE INTO usage(id,owner,day,tokens) SELECT id||':'||attempts,owner,billed_day,reserve FROM jobs WHERE owner=? AND status='running' AND lease_until<? AND reserve>0",
      owner,
      cutoff,
    ),
    sql(
      "UPDATE jobs SET status=CASE WHEN kind='publish' THEN 'uncertain' WHEN attempts>=3 THEN 'failed' ELSE 'queued' END, error='Lease expired; outcome unconfirmed', tokens=tokens+reserve,reserve=0,lease=NULL,lease_until=NULL,scheduled=? WHERE owner=? AND status='running' AND lease_until<?",
      cutoff + 30000,
      owner,
      cutoff,
    ),
  ]);
  await sql(
    "UPDATE jobs SET status='queued',error='' WHERE owner=? AND status='blocked' AND error='A dependency did not complete' AND EXISTS(SELECT 1 FROM jobs d WHERE d.owner=jobs.owner AND d.id=jobs.depends AND d.status='succeeded') AND NOT EXISTS(SELECT 1 FROM jobs p WHERE p.owner=jobs.owner AND p.id=jobs.parent AND p.status='cancelled')",
    owner,
  ).run();
  await sql(
    "UPDATE jobs SET status='blocked',error='A dependency did not complete' WHERE owner=? AND status='queued' AND (depends IN (SELECT id FROM jobs WHERE owner=? AND status IN ('failed','cancelled','blocked','uncertain')) OR parent IN (SELECT id FROM jobs WHERE owner=? AND status='cancelled'))",
    owner,
    owner,
    owner,
  ).run();
}
export async function claim(owner: string, mode: string, token: string) {
  await sweep(owner);
  const existing = await sql(
    "SELECT * FROM jobs WHERE owner=? AND lease=? AND status='running' AND lease_until>?",
    owner,
    token,
    now(),
  ).first<Job>();
  if (existing) return existing;
  // The budget, inherited pause and concurrency checks are inside the atomic claim.
  return sql(
    `UPDATE jobs SET status='running',lease=?,lease_until=?,attempts=attempts+1,
    reserve=CASE WHEN mode='live' AND kind!='publish' THEN 20000 ELSE 0 END,billed_day=?
    WHERE owner=? AND NOT EXISTS(SELECT 1 FROM jobs previous WHERE previous.owner=jobs.owner AND previous.lease=?) AND id=(
      SELECT j.id FROM jobs j JOIN settings s ON s.owner=j.owner JOIN agents a ON a.owner=j.owner AND a.id=j.agent
      WHERE j.owner=? AND j.mode=? AND j.status='queued' AND j.scheduled<=? AND j.attempts<3 AND s.paused=0
      AND (j.depends IS NULL OR EXISTS(SELECT 1 FROM jobs d WHERE d.owner=j.owner AND d.id=j.depends AND d.status='succeeded'))
      AND NOT EXISTS (WITH RECURSIVE tree AS (SELECT id,parent,paused,concurrency FROM agents WHERE owner=j.owner AND id=j.agent UNION ALL SELECT p.id,p.parent,p.paused,p.concurrency FROM agents p JOIN tree t ON p.id=t.parent WHERE p.owner=j.owner) SELECT 1 FROM tree WHERE paused=1)
      AND (SELECT COUNT(*) FROM jobs r WHERE r.owner=j.owner AND r.status='running') < s.concurrency
      AND (SELECT COUNT(*) FROM jobs r WHERE r.owner=j.owner AND r.status='running' AND r.agent=j.agent) < a.concurrency
      AND (j.mode='rehearsal' OR j.kind='publish' OR (SELECT COALESCE(SUM(tokens),0) FROM usage b WHERE b.owner=j.owner AND b.day=?)+(SELECT COALESCE(SUM(reserve),0) FROM jobs b WHERE b.owner=j.owner)+20000 <= s.daily_tokens)
      AND (j.kind!='publish' OR (j.approved=1 AND EXISTS(SELECT 1 FROM accounts c JOIN assets m ON m.id=j.asset AND m.owner=j.owner WHERE c.id=j.account AND c.owner=j.owner AND c.authorized=1 AND c.paused=0 AND (m.expires IS NULL OR m.expires>?) AND m.rights IN ('original','licensed','public-domain')
        AND NOT EXISTS(SELECT 1 FROM jobs p WHERE p.owner=j.owner AND p.account=j.account AND p.status IN ('running','uncertain'))
        AND (SELECT COUNT(*) FROM jobs p WHERE p.owner=j.owner AND p.account=j.account AND p.kind='publish' AND p.status='succeeded' AND p.billed_day=?) < c.daily_limit)))
      ORDER BY j.scheduled,j.created,j.id LIMIT 1
    ) AND status='queued' RETURNING *`,
    token,
    now() + 180000,
    day(),
    owner,
    token,
    owner,
    mode,
    now(),
    day(),
    now(),
    day(),
  ).first<Job>();
}
export async function jobContext(owner: string, j: Job) {
  const agent = await sql(
    "SELECT * FROM agents WHERE owner=? AND id=?",
    owner,
    j.agent,
  ).first<Agent>();
  const dependency = j.depends
    ? await sql(
        "SELECT result FROM jobs WHERE owner=? AND id=?",
        owner,
        j.depends,
      ).first<{ result: string }>()
    : null;
  const account = j.account
    ? await sql(
        "SELECT * FROM accounts WHERE owner=? AND id=?",
        owner,
        j.account,
      ).first()
    : null;
  return { job: j, agent, dependency: dependency?.result ?? "", account };
}
