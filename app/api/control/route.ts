import { xCaption } from "../../../lib/x-text";
import { z } from "zod";
import { updateAgent } from "../../../lib/network";
import { identity, ApiError, failure, response, hash } from "../../../lib/auth";
import {
  state,
  db,
  sql,
  event,
  newJob,
  now,
  claim,
  jobContext,
} from "../../../lib/store";
import {
  workflowInput,
  scheduleInput,
  agentInput,
  lanes,
  accountInput,
  planInput,
  rightsValid,
  type Job,
  type Asset,
} from "../../../lib/domain";
export const dynamic = "force-dynamic";
export async function GET(request: Request) {
  try {
    const { owner, machine } = await identity(request);
    if (machine)
      throw new ApiError("Worker keys cannot read the control room", 403);
    const url = new URL(request.url);
    const offset = z.coerce
      .number()
      .int()
      .min(0)
      .max(1000000)
      .parse(url.searchParams.get("offset") || 0);
    if (url.searchParams.get("picker") === "accounts") {
      const q = (url.searchParams.get("q") || "").slice(0, 120);
      const purpose = ["production", "routing"].includes(
        url.searchParams.get("purpose") || "",
      )
        ? url.searchParams.get("purpose")!
        : "publish";
      const lane = url.searchParams.get("lane") || "";
      if (lane) z.enum(lanes).parse(lane);
      const r = await db().batch([
        sql(
          "SELECT id,handle,external_id,platform FROM accounts WHERE owner=? AND (?!='publish' OR platform IN ('youtube','x')) AND authorized=1 AND (paused=0 OR ?='routing') AND (?='' OR lane=?) AND (instr(lower(handle),lower(?))>0 OR instr(external_id,?)>0) ORDER BY created DESC,id LIMIT 60 OFFSET ?",
          owner,
          purpose,
          purpose,
          lane,
          lane,
          q,
          q,
          offset,
        ),
        sql(
          "SELECT COUNT(*) AS n FROM accounts WHERE owner=? AND (?!='publish' OR platform IN ('youtube','x')) AND authorized=1 AND (paused=0 OR ?='routing') AND (?='' OR lane=?) AND (instr(lower(handle),lower(?))>0 OR instr(external_id,?)>0)",
          owner,
          purpose,
          purpose,
          lane,
          lane,
          q,
          q,
        ),
      ]);
      return response({
        items: r[0].results,
        total: (r[1].results[0] as { n: number }).n,
      });
    }
    return response(
      await state(
        owner,
        offset,
        (url.searchParams.get("q") || "").slice(0, 120),
      ),
    );
  } catch (e) {
    return failure(e);
  }
}
async function complete(owner: string, body: Record<string, unknown>) {
  const v = z
    .object({
      id: z.string().max(100),
      lease: z.string().uuid(),
      status: z.enum(["succeeded", "failed", "uncertain"]),
      result: z.string().max(20000).default(""),
      error: z.string().max(1000).default(""),
      tokens: z.number().int().min(0).max(20000).default(0),
      receipt: z.string().max(500).default(""),
      plan: planInput.optional(),
    })
    .parse(body);
  const j = await sql(
    "SELECT * FROM jobs WHERE owner=? AND id=?",
    owner,
    v.id,
  ).first<Job & { completion_hash: string | null; billed_day: number }>();
  const completionHash = await hash(JSON.stringify(v));
  const nonce = crypto.randomUUID();
  if (!j || j.lease !== v.lease)
    throw new ApiError("This lease is no longer valid", 409);
  if (j.status === v.status && j.completion_hash === completionHash)
    return response({ ok: true });
  if (j.status !== "running" || (j.lease_until || 0) < now())
    throw new ApiError("This lease is no longer valid", 409);
  if (j.kind === "plan" && v.status === "succeeded" && !v.plan)
    throw new ApiError("Astra must return a valid bounded plan");
  if (j.kind === "publish" && v.status === "succeeded" && !v.receipt)
    throw new ApiError("A provider receipt is required");
  const charge =
    j.mode === "rehearsal"
      ? 0
      : v.status === "succeeded"
        ? v.tokens
        : j.reserve;
  const statements = [
    sql(
      "UPDATE jobs SET status=?,result=?,error=?,tokens=tokens+?,reserve=0,receipt=?,completion_nonce=?,completion_hash=? WHERE owner=? AND id=? AND status='running' AND lease=? AND lease_until>?",
      v.status,
      v.result,
      v.error,
      charge,
      v.receipt,
      nonce,
      completionHash,
      owner,
      j.id,
      v.lease,
      now(),
    ),
  ];
  if (j.kind === "plan" && v.status === "succeeded") {
    let previous: string | null = null;
    for (const [i, t] of v.plan!.entries()) {
      const id = `${j.id}-${i}`,
        agent = t.role === "lead" ? j.lane : `${j.lane}-${t.role}`;
      statements.push(
        sql(
          "INSERT OR IGNORE INTO jobs(id,owner,parent,depends,agent,title,brief,lane,mode,kind,status,created,scheduled,account,schedule_id,occurrence) SELECT ?,?,?,?,COALESCE((SELECT agent FROM agent_routes WHERE owner=? AND scope=? AND role=?),(SELECT agent FROM agent_routes WHERE owner=? AND scope=? AND role=?),?),?,?,?,?,?,?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE owner=? AND id=? AND status='succeeded' AND completion_nonce=?)",
          id,
          owner,
          j.id,
          previous,
          owner,
          j.account ? `account:${j.account}` : "none",
          t.role,
          owner,
          `studio:${j.lane}`,
          t.role,
          agent,
          t.title,
          t.brief,
          j.lane,
          j.mode,
          "draft",
          "queued",
          now() + i,
          now(),
          j.account,
          j.schedule_id,
          j.occurrence,
          owner,
          j.id,
          nonce,
        ),
      );
      previous = id;
    }
  }
  statements.push(
    sql(
      "INSERT OR IGNORE INTO usage(id,owner,day,tokens) SELECT ?,?,?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE owner=? AND id=? AND completion_nonce=?)",
      `${j.id}:${j.attempts}`,
      owner,
      j.billed_day,
      charge,
      owner,
      j.id,
      nonce,
    ),
  );
  statements.push(
    sql(
      "INSERT OR IGNORE INTO events(id,owner,type,message,job,created) SELECT ?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM jobs WHERE owner=? AND id=? AND status=? AND completion_nonce=?)",
      `${j.id}-attempt-${j.attempts}`,
      owner,
      v.status,
      `${j.title}: ${v.status}`,
      j.id,
      now(),
      owner,
      j.id,
      v.status,
      nonce,
    ),
  );
  const result = await db().batch(statements);
  if (!result[0].meta.changes)
    throw new ApiError("Completion lost its lease", 409);
  return response({ ok: true });
}
// SQLite changes() refers to the immediately preceding mutation in the D1 batch.
// Keeping the control and its audit event in one transaction prevents false failures
// after a control has already taken effect.
function scheduleControlEvent(owner: string, message: string) {
  return sql(
    "INSERT INTO events(id,owner,type,message,created) SELECT ?,?,'schedule',?,? WHERE changes()>0",
    crypto.randomUUID(),
    owner,
    message,
    now(),
  );
}
export async function POST(request: Request) {
  try {
    const { owner, machine } = await identity(request);
    if (Number(request.headers.get("content-length") || 0) > 40000)
      throw new ApiError("Request too large", 413);
    const raw = await request.text();
    if (new TextEncoder().encode(raw).length > 40000)
      throw new ApiError("Request too large", 413);
    const body = JSON.parse(raw);
    const action = z.string().parse(body.action);
    const machineActions = ["claim", "heartbeat", "complete", "preflight"];
    if (machine !== machineActions.includes(action))
      throw new ApiError(
        "This action is not available for this credential",
        403,
      );
    if (action === "claim") {
      const token = z.string().uuid().parse(body.request_id);
      await sql(
        "UPDATE settings SET worker_seen=? WHERE owner=?",
        now(),
        owner,
      ).run();
      const j = await claim(owner, "live", token);
      return response(j ? await jobContext(owner, j) : { job: null });
    }
    if (action === "heartbeat") {
      const v = z
        .object({ id: z.string().max(100), lease: z.string().uuid() })
        .parse(body);
      const result = await sql(
        "UPDATE jobs SET lease_until=? WHERE owner=? AND id=? AND lease=? AND status='running' AND lease_until>?",
        now() + 180000,
        owner,
        v.id,
        v.lease,
        now(),
      ).run();
      if (!result.meta.changes)
        throw new ApiError("Lease expired or revoked", 409);
      await sql(
        "UPDATE settings SET worker_seen=? WHERE owner=?",
        now(),
        owner,
      ).run();
      return response({ ok: true });
    }
    if (action === "complete") return await complete(owner, body);
    if (action === "preflight") {
      const j = await sql(
        "SELECT j.id FROM jobs j JOIN settings s ON s.owner=j.owner JOIN accounts a ON a.id=j.account AND a.owner=j.owner JOIN assets m ON m.id=j.asset AND m.owner=j.owner WHERE j.owner=? AND j.id=? AND j.lease=? AND j.status='running' AND j.lease_until>? AND j.approved=1 AND s.paused=0 AND a.paused=0 AND a.authorized=1 AND (m.expires IS NULL OR m.expires>?) AND NOT EXISTS(WITH RECURSIVE tree AS (SELECT id,parent,paused,archived FROM agents WHERE owner=j.owner AND id=j.agent UNION ALL SELECT p.id,p.parent,p.paused,p.archived FROM agents p JOIN tree t ON p.id=t.parent WHERE p.owner=j.owner) SELECT 1 FROM tree WHERE paused=1 OR archived=1)",
        owner,
        String(body.id),
        String(body.lease),
        now(),
        now(),
      ).first();
      if (!j)
        throw new ApiError("Publishing is paused or no longer authorized", 409);
      return response({ ok: true });
    }
    if (action === "workflow") {
      const v = workflowInput.parse(body);
      const id = crypto.randomUUID();
      await db().batch([
        newJob(owner, { ...v, id, agent: "astra", kind: "plan" }),
        event(owner, "queued", `Queued ${v.mode} workflow: ${v.title}`, id),
      ]);
      return response({ id });
    }
    if (action === "schedule") {
      const v = scheduleInput.parse(body),
        timestamp = now();
      const id = v.id || v.request_id!;
      const statement = v.id
        ? sql(
            `UPDATE schedules SET title=?,brief=?,mode=?,interval_minutes=?,next_run=?,max_runs=?,paused=?,revision=revision+1,updated=?
            WHERE owner=? AND id=? AND account=? AND revision=?
            AND NOT EXISTS(SELECT 1 FROM jobs history WHERE history.owner=schedules.owner AND history.schedule_id=schedules.id AND history.parent IS NULL AND history.occurrence=?)`,
            v.title,
            v.brief,
            v.mode,
            v.interval_minutes,
            v.next_run,
            v.max_runs,
            +v.paused,
            timestamp,
            owner,
            id,
            v.account,
            v.revision!,
            v.next_run,
          )
        : sql(
            `INSERT OR IGNORE INTO schedules(id,owner,account,title,brief,mode,interval_minutes,next_run,max_runs,paused,created,updated)
            SELECT ?,?,?,?,?,?,?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM accounts WHERE owner=? AND id=? AND authorized=1)
            AND (SELECT COUNT(*) FROM schedules WHERE owner=?)<10000`,
            id,
            owner,
            v.account,
            v.title,
            v.brief,
            v.mode,
            v.interval_minutes,
            v.next_run,
            v.max_runs,
            +v.paused,
            timestamp,
            timestamp,
            owner,
            v.account,
            owner,
          );
      const result = await db().batch([
        statement,
        scheduleControlEvent(
          owner,
          `${v.id ? "Updated" : "Created"} recurring workflow: ${v.title}`,
        ),
      ]);
      if (!result[0].meta.changes) {
        // Creation request IDs are stable across retries: the first saved request wins.
        const replay =
          !v.id &&
          (await sql(
            "SELECT id FROM schedules WHERE owner=? AND id=?",
            owner,
            id,
          ).first());
        if (!replay)
          throw new ApiError(
            v.id
              ? "Schedule changed or this start time was already used. Refresh, choose a new time, and keep its account unchanged."
              : "Authorized account unavailable or schedule limit reached",
            409,
          );
      }
      return response({ id });
    }
    if (action === "schedule-pause") {
      const v = z
        .object({
          id: z.string().uuid(),
          revision: z.number().int().positive(),
          paused: z.boolean(),
        })
        .parse(body);
      const result = await db().batch([
        sql(
          "UPDATE schedules SET paused=?,revision=revision+1,updated=? WHERE owner=? AND id=? AND revision=?",
          +v.paused,
          now(),
          owner,
          v.id,
          v.revision,
        ),
        scheduleControlEvent(
          owner,
          v.paused
            ? "Recurring workflow paused; waiting tasks held and running calls may finish"
            : "Recurring workflow resumed",
        ),
      ]);
      if (!result[0].meta.changes)
        throw new ApiError(
          "Schedule changed. Refresh before changing its pause control.",
          409,
        );
      return response({ ok: true });
    }
    if (action === "schedule-discard") {
      const v = z
        .object({
          id: z.string().uuid(),
          occurrence: z.number().int().nonnegative(),
        })
        .parse(body);
      const result = await db().batch([
        sql(
          `UPDATE jobs SET status='cancelled',error='Occurrence discarded by operator'
        WHERE owner=? AND schedule_id=? AND occurrence=? AND status IN ('queued','blocked','failed')
        AND NOT EXISTS(SELECT 1 FROM jobs active WHERE active.owner=jobs.owner AND active.schedule_id=jobs.schedule_id
          AND active.occurrence=jobs.occurrence AND active.status IN ('running','uncertain'))`,
          owner,
          v.id,
          v.occurrence,
        ),
        scheduleControlEvent(
          owner,
          "Waiting occurrence discarded; future recurrence remains scheduled",
        ),
      ]);
      if (!result[0].meta.changes)
        throw new ApiError(
          "This run is active, uncertain, or has no waiting tasks. Pause and let running calls finish first.",
          409,
        );
      return response({ ok: true });
    }
    if (action === "agent") {
      await updateAgent(owner, agentInput.parse(body));
      return response({ ok: true });
    }
    if (action === "settings") {
      const v = z
        .object({
          paused: z.boolean(),
          concurrency: z.number().int().min(1).max(32),
          daily_tokens: z.number().int().min(20000).max(10000000),
        })
        .parse(body);
      await db().batch([
        sql(
          "UPDATE settings SET paused=?,concurrency=?,daily_tokens=? WHERE owner=?",
          +v.paused,
          v.concurrency,
          v.daily_tokens,
          owner,
        ),
        event(
          owner,
          "control",
          v.paused
            ? "Workspace paused; current calls may finish"
            : "Updated workspace execution limits",
        ),
      ]);
      return response({ ok: true });
    }
    if (action === "worker-key") {
      const token =
        "cs_" +
        Array.from(crypto.getRandomValues(new Uint8Array(32)))
          .map((x) => x.toString(16).padStart(2, "0"))
          .join("");
      await db().batch([
        sql(
          "UPDATE settings SET worker_hash=?,worker_seen=NULL WHERE owner=?",
          await hash(token),
          owner,
        ),
        event(owner, "control", "Worker key rotated; previous key revoked"),
      ]);
      return response({ token });
    }
    if (action === "revoke-key") {
      await db().batch([
        sql(
          "UPDATE settings SET worker_hash=NULL,worker_seen=NULL WHERE owner=?",
          owner,
        ),
        event(owner, "control", "Worker access revoked"),
      ]);
      return response({ ok: true });
    }
    if (action === "account") {
      const v = accountInput.parse(body);
      const id = crypto.randomUUID();
      const total = await sql(
        "SELECT COUNT(*) AS n FROM accounts WHERE owner=?",
        owner,
      ).first<{ n: number }>();
      if ((total?.n || 0) >= 10000)
        throw new ApiError("Registry limit reached");
      try {
        await db().batch([
          sql(
            "INSERT INTO accounts(id,owner,platform,handle,lane,external_id,credential_ref,authorized,daily_limit,created) VALUES(?,?,?,?,?,?,?,?,?,?)",
            id,
            owner,
            v.platform,
            v.handle,
            v.lane,
            v.external_id,
            v.credential_ref,
            1,
            v.daily_limit,
            now(),
          ),
          event(
            owner,
            "account",
            `Registered ${v.platform} account ${v.handle}; credentials still need configuration`,
          ),
        ]);
      } catch {
        throw new ApiError(
          "This platform account is already registered or could not be saved",
          409,
        );
      }
      return response({ id });
    }
    if (action === "account-pause") {
      const v = z
        .object({ id: z.string().uuid(), paused: z.boolean() })
        .parse(body);
      await db().batch([
        sql(
          "UPDATE accounts SET paused=? WHERE owner=? AND id=?",
          +v.paused,
          owner,
          v.id,
        ),
        event(
          owner,
          "control",
          v.paused
            ? "Account production and publishing paused"
            : "Account production and publishing resumed",
        ),
      ]);
      return response({ ok: true });
    }
    if (action === "cancel") {
      const id = z.string().max(100).parse(body.id);
      const result = await sql(
        "UPDATE jobs SET status='cancelled',error='Cancelled by operator' WHERE owner=? AND id=? AND status IN ('queued','blocked','failed')",
        owner,
        id,
      ).run();
      if (!result.meta.changes)
        throw new ApiError(
          "Only tasks that have not started can be cancelled. Pause to drain running work.",
          409,
        );
      await db().batch([
        sql(
          "UPDATE jobs SET status='cancelled',error='Parent cancelled' WHERE owner=? AND parent=? AND status IN ('queued','blocked')",
          owner,
          id,
        ),
        event(owner, "control", "Task cancelled", id),
      ]);
      return response({ ok: true });
    }
    if (action === "retry") {
      const id = z.string().max(100).parse(body.id);
      const r = await sql(
        "UPDATE jobs SET status='queued',error='',scheduled=? WHERE owner=? AND id=? AND status='failed' AND kind!='publish' AND attempts<3",
        now(),
        owner,
        id,
      ).run();
      if (!r.meta.changes)
        throw new ApiError(
          "Task cannot be retried. Publishing and exhausted retries require review.",
          409,
        );
      await event(
        owner,
        "control",
        "Task queued for a bounded retry",
        id,
      ).run();
      return response({ ok: true });
    }
    if (action === "publish") {
      const v = z
        .object({
          title: z.string().min(3).max(100),
          brief: z.string().min(1).max(4500),
          account: z.string().uuid(),
          asset: z.string().uuid(),
          scheduled: z.number().int().min(0),
          approved: z.literal(true),
          approval_scope: z
            .enum(["youtube-private", "x-account"])
            .default("youtube-private"),
          made_with_ai: z.boolean().default(false),
        })
        .parse(body);
      const a = await sql(
        "SELECT * FROM accounts WHERE owner=? AND id=?",
        owner,
        v.account,
      ).first<{
        platform: string;
        lane: string;
        paused: number;
        authorized: number;
        external_id: string;
      }>();
      const m = await sql(
        "SELECT * FROM assets WHERE owner=? AND id=?",
        owner,
        v.asset,
      ).first<Asset>();
      if (!a || !m) throw new ApiError("Account or media not found", 404);
      if (!["youtube", "x"].includes(a.platform))
        throw new ApiError(
          "This platform currently requires a manual publishing handoff",
        );
      if (
        v.approval_scope !==
        (a.platform === "x" ? "x-account" : "youtube-private")
      )
        throw new ApiError(
          "Review and approve the selected platform’s audience before scheduling",
        );
      if (a.platform === "x" && !/^[0-9]{1,19}$/.test(a.external_id))
        throw new ApiError(
          "X publishing requires the account’s numeric user ID",
        );
      if (a.platform === "x" && !xCaption(v.brief).valid)
        throw new ApiError(
          "X caption exceeds 280 weighted characters or contains invalid text",
        );
      if (
        a.paused ||
        !a.authorized ||
        !rightsValid(m, Math.max(now(), v.scheduled))
      )
        throw new ApiError(
          "Account is paused or content rights are missing/expired",
        );
      const duplicate = await sql(
        "SELECT id FROM jobs WHERE owner=? AND asset=? AND kind='publish' AND status IN ('queued','running','uncertain','succeeded')",
        owner,
        v.asset,
      ).first();
      if (duplicate)
        throw new ApiError(
          "This media already has a publication. Review its receipt before creating another.",
          409,
        );
      const id = crypto.randomUUID();
      await db().batch([
        newJob(owner, {
          ...v,
          id,
          agent: `${a.lane}-editor`,
          lane: a.lane,
          kind: "publish",
          mode: "live",
          approved: 1,
          made_with_ai: a.platform === "x" ? +v.made_with_ai : 0,
        }),
        event(
          owner,
          "approval",
          `${a.platform === "x" ? "Approved X post to the account audience" : "Approved private YouTube upload"}: ${v.title}`,
          id,
        ),
      ]);
      return response({ id });
    }
    if (action === "reconcile") {
      const v = z
        .object({
          id: z.string().max(100),
          receipt: z.string().trim().min(3).max(500),
        })
        .parse(body);
      const r = await sql(
        "UPDATE jobs SET status='succeeded',receipt=?,error='' WHERE owner=? AND id=? AND kind='publish' AND status='uncertain'",
        v.receipt,
        owner,
        v.id,
      ).run();
      if (!r.meta.changes)
        throw new ApiError("Only uncertain uploads can be reconciled", 409);
      await event(
        owner,
        "control",
        "Operator recorded verified provider receipt",
        v.id,
      ).run();
      return response({ ok: true });
    }
    if (action === "rehearse") {
      const j = await claim(owner, "rehearsal", crypto.randomUUID());
      if (!j)
        return response({
          message:
            "No eligible rehearsal task. Check schedules, pauses and dependencies.",
        });
      const plan =
        j.kind === "plan"
          ? [
              {
                role: "lead",
                title: `Production brief: ${j.title}`,
                brief: j.brief,
              },
              {
                role: "writer",
                title: `Script: ${j.title}`,
                brief: `Write an original script for this brief: ${j.brief}`,
              },
              {
                role: "editor",
                title: `Editorial package: ${j.title}`,
                brief: `Review the draft and prepare a publishing package for ${j.title}.`,
              },
            ].map((t) => ({
              ...t,
              title: t.title.slice(0, 160),
              brief: t.brief.slice(0, 6000),
            }))
          : undefined;
      return await complete(owner, {
        id: j.id,
        lease: j.lease,
        status: "succeeded",
        tokens: 0,
        plan,
        result:
          j.kind === "plan"
            ? "REHEARSAL · Deterministic plan, no model was called.\nDelegated a production brief, script and editorial review to the selected studio."
            : `REHEARSAL · No model was called and no media was rendered.\n\nTask: ${j.title}\nBrief: ${j.brief}\n\nThis result verifies task dispatch, dependencies, completion and the audit trail. Connect a worker and use a live workflow for actual model output.`,
      });
    }
    throw new ApiError("Unknown action");
  } catch (e) {
    if (e instanceof SyntaxError)
      return response({ error: "Invalid JSON" }, 400);
    return failure(e);
  }
}
