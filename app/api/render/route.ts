import { z } from "zod";
import { identity, ApiError, failure, response } from "../../../lib/auth";
import { bucket, db, sql, now } from "../../../lib/store";
import { renderPreflight, renderEligibility } from "../../../lib/render";

const MAX = 16 * 1024 * 1024;
async function boundedForm(request: Request) {
  if (Number(request.headers.get("content-length") || 0) > MAX + 12000)
    throw new ApiError("Rendered media exceeds its upload limit", 413);
  const reader = request.body?.getReader();
  if (!reader) throw new ApiError("Rendered media is missing");
  const chunks: Uint8Array[] = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX + 12000) {
      await reader.cancel();
      throw new ApiError("Rendered media exceeds its upload limit", 413);
    }
    chunks.push(value);
  }
  const body = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.length;
  }
  return new Response(body, {
    headers: { "Content-Type": request.headers.get("content-type") || "" },
  }).formData();
}

export async function POST(request: Request) {
  try {
    const { owner, machine, worker } = await identity(request);
    if (!machine || !worker)
      throw new ApiError(
        "Only the leased rendering worker can save generated media",
        403,
      );
    const id = z.string().uuid().parse(request.headers.get("x-render-job"));
    const lease = z
      .string()
      .uuid()
      .parse(request.headers.get("x-render-lease"));
    const { spec, asset: existing } = await renderPreflight(
      owner,
      worker,
      id,
      lease,
    );
    if (existing)
      return response({ asset: existing.id, sha256: existing.sha256 });
    const form = await boundedForm(request),
      file = form.get("file");
    if (!(file instanceof File) || file.size < 12 || file.size > MAX)
      throw new ApiError("Choose a rendered MP4 up to 16 MiB");
    const bytes = await file.arrayBuffer();
    if (String.fromCharCode(...new Uint8Array(bytes).slice(4, 8)) !== "ftyp")
      throw new ApiError("Rendered output is not an MP4 container");
    const digest = Array.from(
      new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
    )
      .map((x) => x.toString(16).padStart(2, "0"))
      .join("");
    if (form.get("sha256") !== digest)
      throw new ApiError("Rendered media digest does not match");
    const candidate = crypto.randomUUID(),
      key = `${owner}/${candidate}.mp4`,
      name = `ambient-${spec.noise}-${id}.mp4`;
    const evidence = spec.script
      ? "Original procedural ambient color video, synthesized noise and the operator-approved original narration script. Generated locally; no third-party footage, soundtrack or voice recording."
      : `Original procedural ${spec.theme} color video and synthesized ${spec.noise} noise; ${spec.seconds} seconds, seed ${spec.seed}. Rendered by the authorized worker with FFmpeg, without third-party footage or soundtrack. SHA-256: ${digest}.`;
    await bucket().put(key, bytes, {
      httpMetadata: { contentType: "video/mp4" },
    });
    // Every upload attempt has a distinct private key. A losing attempt cannot overwrite the winner.
    try {
      const cutoff = now();
      await db().batch([
        sql(
          `INSERT OR IGNORE INTO assets(id,owner,name,object_key,mime,size,rights,evidence,expires,created,source_job,sha256)
          SELECT ?,?,?,?,'video/mp4',?,'original',?,NULL,?,?,? WHERE EXISTS(${renderEligibility})`,
          candidate,
          owner,
          name,
          key,
          file.size,
          evidence,
          cutoff,
          id,
          digest,
          owner,
          worker,
          id,
          lease,
          cutoff,
        ),
        sql(
          `UPDATE jobs SET asset=(SELECT id FROM assets WHERE owner=? AND source_job=?) WHERE owner=? AND id=? AND EXISTS(${renderEligibility})`,
          owner,
          id,
          owner,
          id,
          owner,
          worker,
          id,
          lease,
          cutoff,
        ),
        sql(
          "INSERT OR IGNORE INTO events(id,owner,type,message,job,created) SELECT ?,?,'media',?,?,? WHERE EXISTS(SELECT 1 FROM assets WHERE id=? AND owner=?)",
          `render-media-${id}`,
          owner,
          `Generated original ${spec.noise} noise video`,
          id,
          cutoff,
          candidate,
          owner,
        ),
      ]);
    } catch (e) {
      // Do not delete potentially committed media after an ambiguous database response.
      try {
        const saved = await sql(
          "SELECT id FROM assets WHERE id=? AND owner=?",
          candidate,
          owner,
        ).first();
        if (!saved) await bucket().delete(key);
      } catch {}
      throw e;
    }
    const saved = await sql(
      "SELECT id,sha256 FROM assets WHERE owner=? AND source_job=?",
      owner,
      id,
    ).first<{ id: string; sha256: string }>();
    if (saved?.id !== candidate) await bucket().delete(key);
    if (!saved)
      throw new ApiError(
        "Rendering was paused or the lease expired before media was saved",
        409,
      );
    return response({ asset: saved.id, sha256: saved.sha256 });
  } catch (e) {
    return failure(e);
  }
}
