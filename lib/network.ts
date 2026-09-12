import { z } from "zod";
import { db, sql, now } from "./store";
import { ApiError } from "./auth";
import { agentInput, lanes, type Agent, type NetworkAgent } from "./domain";

const role = z.enum(["lead", "writer", "editor"]);
const id = z
  .string()
  .min(1)
  .max(100)
  .regex(/^[a-zA-Z0-9_-]+$/);
export const createAgentInput = z.object({
  request_id: z.string().uuid(),
  parent: id,
  name: z.string().trim().min(2).max(80),
  task_role: role,
  model: agentInput.shape.model,
  instructions: agentInput.shape.instructions,
  concurrency: agentInput.shape.concurrency,
  paused: z.boolean(),
});
export const routeInput = z.object({
  lane: z.enum(lanes),
  role,
  account: z.string().uuid().nullable(),
  agent: id.nullable(),
  revision: z.number().int().min(0),
});
export function networkAudit(owner: string, message: string) {
  return sql(
    "INSERT INTO events(id,owner,type,message,created) SELECT ?,?,'network',?,? WHERE changes()>0",
    crypto.randomUUID(),
    owner,
    message,
    now(),
  );
}

export async function createAgent(
  owner: string,
  v: z.infer<typeof createAgentInput>,
) {
  const result = await db().batch([
    sql(
      `INSERT OR IGNORE INTO agents(owner,id,parent,name,role,lane,model,paused,concurrency,instructions,color,task_role,core,archived,depth,revision,child_count,search_name)
      SELECT ?,?,p.id,?,?,p.lane,?,?,?,?,p.color,?,0,0,p.depth+1,1,0,?
      FROM agents p JOIN settings w ON w.owner=p.owner
      WHERE p.owner=? AND p.id=? AND p.archived=0 AND p.depth>=1 AND p.depth<8
        AND w.agent_total<1000000`,
      owner,
      v.request_id,
      v.name,
      v.task_role,
      v.model,
      +v.paused,
      v.concurrency,
      v.instructions,
      v.task_role,
      v.name.toLowerCase(),
      owner,
      v.parent,
    ),
    sql(
      "UPDATE agents SET child_count=child_count+1 WHERE owner=? AND id=? AND changes()>0",
      owner,
      v.parent,
    ),
    sql(
      "UPDATE settings SET agent_total=agent_total+1 WHERE owner=? AND changes()>0",
      owner,
    ),
    networkAudit(
      owner,
      `Created agent configuration: ${v.name}; assign a routing role to receive work`,
    ),
  ]);
  if (
    !result[0].meta.changes &&
    !(await sql(
      "SELECT id FROM agents WHERE owner=? AND id=?",
      owner,
      v.request_id,
    ).first())
  )
    throw new ApiError(
      "Choose an available studio branch below depth eight; the configuration capacity may be reached",
      409,
    );
  return { id: v.request_id };
}
export async function updateAgent(
  owner: string,
  v: z.infer<typeof agentInput>,
) {
  if (v.id === "astra" && v.model !== "gpt-6-astra")
    throw new ApiError("The head orchestrator is fixed to gpt-6-astra");
  const result = await db().batch([
    sql(
      "UPDATE agents SET paused=?,concurrency=?,model=?,instructions=?,revision=revision+1 WHERE owner=? AND id=? AND revision=? AND archived=0",
      +v.paused,
      v.concurrency,
      v.model,
      v.instructions,
      owner,
      v.id,
      v.revision,
    ),
    networkAudit(owner, `Updated agent ${v.id}`),
  ]);
  if (!result[0].meta.changes)
    throw new ApiError(
      "Agent changed or is retired. Refresh its configuration before editing.",
      409,
    );
}
export async function retireAgent(owner: string, body: unknown) {
  const v = z
    .object({
      id,
      revision: z.number().int().positive(),
      archived: z.boolean(),
    })
    .parse(body);
  const query = v.archived
    ? `UPDATE agents SET archived=1,paused=1,revision=revision+1 WHERE owner=? AND id=? AND revision=? AND core=0 AND archived=0
        AND NOT EXISTS(SELECT 1 FROM agents child WHERE child.owner=agents.owner AND child.parent=agents.id AND child.archived=0)
        AND NOT EXISTS(SELECT 1 FROM agent_routes route WHERE route.owner=agents.owner AND route.agent=agents.id)
        AND NOT EXISTS(SELECT 1 FROM jobs j WHERE j.owner=agents.owner AND j.agent=agents.id AND j.status IN ('queued','running','blocked','failed','uncertain'))`
    : `UPDATE agents SET archived=0,paused=1,revision=revision+1 WHERE owner=? AND id=? AND revision=? AND core=0 AND archived=1
        AND EXISTS(SELECT 1 FROM agents p WHERE p.owner=agents.owner AND p.id=agents.parent AND p.archived=0)
        AND NOT EXISTS(WITH RECURSIVE chain AS (SELECT id,parent,depth,paused,archived FROM agents p WHERE p.owner=agents.owner AND p.id=agents.parent
          UNION ALL SELECT p.id,p.parent,p.depth,p.paused,p.archived FROM agents p JOIN chain c ON p.id=c.parent AND p.depth<c.depth WHERE p.owner=agents.owner)
          SELECT 1 FROM chain WHERE paused=1 OR archived=1)`;
  const result = await db().batch([
    sql(query, owner, v.id, v.revision),
    networkAudit(
      owner,
      v.archived
        ? `Retired agent ${v.id}`
        : `Restored agent ${v.id}; kept paused`,
    ),
  ]);
  if (!result[0].meta.changes)
    throw new ApiError(
      v.archived
        ? "Agent changed, is built in, or still has routing assignments, active children or unfinished work. Resolve those before retirement."
        : "Agent changed or an ancestor is paused/retired. Restore and enable its ancestors first.",
      409,
    );
}

export async function setRoute(owner: string, v: z.infer<typeof routeInput>) {
  const scope = v.account ? `account:${v.account}` : `studio:${v.lane}`;
  const result = await db().batch([
    sql(
      `INSERT INTO agent_routes(owner,scope,role,agent,revision)
      SELECT ?,?,?,?,1
      WHERE (?=0 OR EXISTS(SELECT 1 FROM agent_routes r WHERE r.owner=? AND r.scope=? AND r.role=?))
        AND (? IS NULL OR EXISTS(SELECT 1 FROM agents a WHERE a.owner=? AND a.id=? AND a.lane=? AND a.task_role=? AND a.archived=0))
        AND (? IS NULL OR EXISTS(SELECT 1 FROM accounts c WHERE c.owner=? AND c.id=? AND c.lane=? AND c.authorized=1))
      ON CONFLICT(owner,scope,role) DO UPDATE SET agent=excluded.agent,revision=agent_routes.revision+1
      WHERE agent_routes.revision=?`,
      owner,
      scope,
      v.role,
      v.agent,
      v.revision,
      owner,
      scope,
      v.role,
      v.agent,
      owner,
      v.agent,
      v.lane,
      v.role,
      v.account,
      owner,
      v.account,
      v.lane,
      v.revision,
    ),
    networkAudit(
      owner,
      `Updated ${scope} ${v.role} routing${v.agent ? ` to ${v.agent}` : " to its default"}`,
    ),
  ]);
  if (!result[0].meta.changes)
    throw new ApiError(
      "Routing changed, or the account/agent does not match this studio and role. Refresh before saving.",
      409,
    );
}
export async function readRoutes(
  owner: string,
  lane: string,
  account: string | null,
) {
  const l = z.enum(lanes).parse(lane);
  if (account) {
    z.string().uuid().parse(account);
    if (
      !(await sql(
        "SELECT id FROM accounts WHERE owner=? AND id=? AND lane=? AND authorized=1",
        owner,
        account,
        l,
      ).first())
    )
      throw new ApiError("Account is not authorized for this studio", 404);
  }
  const scope = account ? `account:${account}` : `studio:${l}`;
  const r = await sql(
    "SELECT r.*,a.name AS agent_name FROM agent_routes r LEFT JOIN agents a ON a.owner=r.owner AND a.id=r.agent WHERE r.owner=? AND r.scope=?",
    owner,
    scope,
  ).all();
  return { scope, routes: r.results };
}

// Restrict per-node status work to the bounded set returned to the browser.
export const nodeSelect = `SELECT a.*,
  (SELECT COUNT(*) FROM jobs j WHERE j.owner=a.owner AND j.agent=a.id AND j.status='running') AS running,
  (SELECT COUNT(*) FROM jobs j WHERE j.owner=a.owner AND j.agent=a.id AND j.status='queued') AS queued,
  (SELECT COUNT(*) FROM agent_routes r WHERE r.owner=a.owner AND r.agent=a.id) AS route_count FROM agents a`;
export async function branch(owner: string, focusId: string, after: string) {
  id.parse(focusId);
  if (after) id.parse(after);
  const result = await db().batch([
    sql(`${nodeSelect} WHERE a.owner=? AND a.id=?`, owner, focusId),
    sql(
      `WITH RECURSIVE chain AS(SELECT * FROM agents WHERE owner=? AND id=?
      UNION ALL SELECT p.* FROM agents p JOIN chain c ON p.id=c.parent AND p.depth<c.depth WHERE p.owner=?)
      SELECT * FROM chain WHERE id!=? ORDER BY depth`,
      owner,
      focusId,
      owner,
      focusId,
    ),
    sql(
      `${nodeSelect} WHERE a.owner=? AND a.parent=? AND a.id>? ORDER BY a.id LIMIT 13`,
      owner,
      focusId,
      after,
    ),
    sql("SELECT agent_total FROM settings WHERE owner=?", owner),
  ]);
  const focus = result[0].results[0] as unknown as NetworkAgent;
  if (!focus) throw new ApiError("Agent not found", 404);
  const children = result[2].results as unknown as NetworkAgent[];
  return {
    focus,
    ancestors: result[1].results as unknown as Agent[],
    children: children.slice(0, 12),
    next: children.length > 12 ? children[11].id : null,
    total: Number(
      (result[3].results[0] as { agent_total: number }).agent_total,
    ),
  };
}
export async function searchAgents(owner: string, term: string, after: string) {
  const prefix = z.string().trim().min(1).max(80).parse(term).toLowerCase();
  const letters = Array.from(prefix);
  while (letters.at(-1)?.codePointAt(0) === 0x10ffff) letters.pop();
  const last = letters.pop();
  const nextCode = last === undefined ? null : last.codePointAt(0)! + 1;
  const upper =
    nextCode === null
      ? null
      : letters.join("") +
        String.fromCodePoint(nextCode === 0xd800 ? 0xe000 : nextCode);
  let cursor = [prefix, ""];
  if (after) {
    try {
      cursor = z
        .array(z.string().max(160))
        .length(2)
        .parse(JSON.parse(atob(after)));
      if (!cursor[0].startsWith(prefix)) throw new Error();
      id.parse(cursor[1]);
    } catch {
      throw new ApiError("Invalid search cursor");
    }
  }
  const boundary = upper === null ? "" : "AND a.search_name<?";
  const binds =
    upper === null
      ? [owner, cursor[0], cursor[1]]
      : [owner, cursor[0], cursor[1], upper];
  const rows = await sql(
    `${nodeSelect} WHERE a.owner=? AND (a.search_name,a.id)>(?,?)
    ${boundary} ORDER BY a.search_name,a.id LIMIT 21`,
    ...binds,
  ).all<NetworkAgent & { search_name: string }>();
  const items = rows.results.slice(0, 20);
  // Encode Unicode names safely; decode the matching transport on the next page.
  const next =
    rows.results.length > 20
      ? btoa(
          JSON.stringify([items[19].search_name, items[19].id]).replace(
            /[\u007f-\uffff]/g,
            (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"),
          ),
        )
      : null;
  return { items, next };
}

export async function routeReferences(
  owner: string,
  agent: string,
  after: string,
) {
  id.parse(agent);
  let cursor = ["", ""];
  if (after) {
    try {
      cursor = z
        .array(z.string().max(120))
        .length(2)
        .parse(JSON.parse(atob(after)));
    } catch {
      throw new ApiError("Invalid assignment cursor");
    }
  }
  const rows = await sql(
    `SELECT r.scope,r.role,r.revision,c.handle,c.platform FROM agent_routes r
    LEFT JOIN accounts c ON c.owner=r.owner AND c.id=substr(r.scope,9) AND substr(r.scope,1,8)='account:'
    WHERE r.owner=? AND r.agent=? AND (r.scope,r.role)>(?,?) ORDER BY r.scope,r.role LIMIT 21`,
    owner,
    agent,
    cursor[0],
    cursor[1],
  ).all<{
    scope: string;
    role: string;
    revision: number;
    handle: string | null;
    platform: string | null;
  }>();
  const items = rows.results.slice(0, 20);
  return {
    items,
    next:
      rows.results.length > 20
        ? btoa(JSON.stringify([items[19].scope, items[19].role]))
        : null,
  };
}
