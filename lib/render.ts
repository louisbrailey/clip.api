import { z } from "zod/v3";
import { ApiError } from "./auth";
import { sql, now } from "./store";
import { ambientRecipe, type Job } from "./domain";

export const ambientSpec = ambientRecipe
  .extend({ seed: z.number().int().min(1).max(2147483647) })
  .strict();

export const photoSpec = z.object({
  type: z.literal("photo-video"),
  prompt: z.string().trim().min(1).max(1200),
  mime: z.enum(["image/jpeg", "image/png"]),
  digest: z.string().regex(/^[a-f0-9]{64}$/),
  seed: z.number().int().min(1).max(2147483647),
}).strict();

export function localMediaEnabled(request: Request) {
  return process.env.NODE_ENV === "development" &&
    ["localhost", "127.0.0.1"].includes(new URL(request.url).hostname);
}

export function photoKey(owner: string, id: string, digest: string) {
  return `photo-video/${owner}/${id}/${digest}`;
}

export async function boundedForm(request: Request, max: number) {
  if (Number(request.headers.get("content-length") || 0) > max)
    throw new ApiError("Media exceeds its upload limit", 413);
  const reader = request.body?.getReader();
  if (!reader) throw new ApiError("Media is missing");
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > max) {
      await reader.cancel();
      throw new ApiError("Media exceeds its upload limit", 413);
    }
    chunks.push(value);
  }
  const body = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.length;
  }
  try {
    return await new Response(body, {
      headers: { "Content-Type": request.headers.get("content-type") || "" },
    }).formData();
  } catch {
    throw new ApiError("Invalid media form");
  }
}

// Reused verbatim at preflight and inside the upload transaction.
export const renderEligibility = `SELECT j.* FROM jobs j JOIN settings s ON s.owner=j.owner
WHERE j.owner=? AND j.worker_id=? AND j.id=? AND j.lease=? AND j.lease_until>? AND j.status='running'
AND j.kind='render' AND j.mode='live' AND j.approved=1 AND j.lane='ambient' AND s.paused=0
AND (j.account IS NULL OR EXISTS(SELECT 1 FROM accounts a WHERE a.owner=j.owner AND a.id=j.account AND a.authorized=1 AND a.paused=0))
AND (j.schedule_id IS NULL OR EXISTS(SELECT 1 FROM schedules r WHERE r.owner=j.owner AND r.id=j.schedule_id AND r.paused=0))
AND EXISTS(SELECT 1 FROM agents a WHERE a.owner=j.owner AND a.id=j.agent)
AND NOT EXISTS(WITH RECURSIVE tree AS (SELECT id,parent,paused,archived FROM agents WHERE owner=j.owner AND id=j.agent
UNION ALL SELECT p.id,p.parent,p.paused,p.archived FROM agents p JOIN tree t ON p.id=t.parent WHERE p.owner=j.owner)
SELECT 1 FROM tree WHERE paused=1 OR archived=1)`;

export async function renderPreflight(
  owner: string,
  worker: string,
  id: string,
  lease: string,
) {
  const job = await sql(
    renderEligibility,
    owner,
    worker,
    id,
    lease,
    now(),
  ).first<Job>();
  if (!job)
    throw new ApiError(
      "Rendering is paused or this lease is no longer authorized",
      409,
    );
  const recipe = JSON.parse(job.render_spec || "null");
  const spec = recipe?.type === "photo-video"
    ? photoSpec.parse(recipe)
    : ambientSpec.parse(recipe);
  const asset = await sql(
    "SELECT id,sha256 FROM assets WHERE owner=? AND source_job=?",
    owner,
    id,
  ).first<{ id: string; sha256: string }>();
  return { job, spec, asset };
}
