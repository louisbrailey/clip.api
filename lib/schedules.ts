import { db, sql, now } from "./store";

// Reused inside the insertion, so operator edits between selection and dispatch
// cannot bypass eligibility. Filter before LIMIT to avoid head-of-line starvation.
export const dueSchedules = `SELECT r.id FROM schedules r
  JOIN settings w ON w.owner=r.owner
  JOIN accounts a ON a.owner=r.owner AND a.id=r.account
  JOIN agents h ON h.owner=r.owner AND h.id='astra'
  JOIN agents studio ON studio.owner=r.owner AND studio.id=a.lane
  WHERE r.owner=? AND r.mode=? AND r.next_run<=? AND r.paused=0
    AND w.paused=0 AND a.paused=0 AND a.authorized=1 AND h.paused=0 AND studio.paused=0
    AND (r.production_kind='workflow' OR (r.production_kind='ambient' AND r.mode='live' AND a.lane='ambient' AND r.render_approved=1 AND r.render_recipe IS NOT NULL
      AND EXISTS(SELECT 1 FROM agents editor WHERE editor.owner=r.owner AND editor.id='ambient-editor' AND editor.paused=0 AND editor.archived=0)))
    AND (r.max_runs IS NULL OR r.generated_count<r.max_runs)
    AND NOT EXISTS(SELECT 1 FROM jobs j WHERE j.owner=r.owner AND j.schedule_id=r.id
      AND j.status IN ('queued','running','blocked','failed','uncertain'))
  ORDER BY r.next_run,r.id LIMIT 10`;

export async function expandSchedules(owner: string, mode: string) {
  const cutoff = now();
  const candidates = await sql(dueSchedules, owner, mode, cutoff).all<{
    id: string;
  }>();
  for (const candidate of candidates.results) {
    const id = crypto.randomUUID(),
      seed = 1 + (crypto.getRandomValues(new Uint32Array(1))[0] % 2147483647);
    // One D1 transaction: create a snapshot, then move only its own occurrence.
    // Missed intervals coalesce into one run while preserving the original cadence.
    await db().batch([
      sql(
        `INSERT OR IGNORE INTO jobs(id,owner,agent,title,brief,lane,mode,kind,status,created,scheduled,account,schedule_id,occurrence,approved,render_spec)
        SELECT ?,r.owner,CASE WHEN r.production_kind='ambient' THEN 'ambient-editor' ELSE 'astra' END,r.title,r.brief,a.lane,r.mode,
        CASE WHEN r.production_kind='ambient' THEN 'render' ELSE 'plan' END,'queued',?,?,r.account,r.id,r.next_run,
        CASE WHEN r.production_kind='ambient' THEN 1 ELSE 0 END,
        CASE WHEN r.production_kind='ambient' THEN json_set(r.render_recipe,'$.seed',CAST(? AS INTEGER)) ELSE NULL END
        FROM schedules r JOIN accounts a ON a.owner=r.owner AND a.id=r.account
        WHERE r.owner=? AND r.id=? AND r.id IN (${dueSchedules})`,
        id,
        cutoff,
        cutoff,
        seed,
        owner,
        candidate.id,
        owner,
        mode,
        cutoff,
      ),
      sql(
        `UPDATE schedules SET
        next_run=next_run+(CAST((?-next_run)/(interval_minutes*60000) AS INTEGER)+1)*interval_minutes*60000,
        generated_count=generated_count+1,revision=revision+1,updated=?
        WHERE owner=? AND id=? AND EXISTS(SELECT 1 FROM jobs j WHERE j.id=? AND j.owner=schedules.owner
          AND j.schedule_id=schedules.id AND j.parent IS NULL AND j.occurrence=schedules.next_run)`,
        cutoff,
        cutoff,
        owner,
        candidate.id,
        id,
      ),
      sql(
        `INSERT OR IGNORE INTO events(id,owner,type,message,job,created)
        SELECT ?||'-scheduled',owner,'scheduled','Recurring workflow queued: '||title,id,?
        FROM jobs WHERE owner=? AND id=?`,
        id,
        cutoff,
        owner,
        id,
      ),
    ]);
  }
}
