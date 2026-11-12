import { z } from "zod/v3";
import { ApiError, failure, identity, response } from "../../../lib/auth";
import { boundedForm, localMediaEnabled, photoKey, photoSpec, renderPreflight } from "../../../lib/render";
import { bucket, db, now, sql } from "../../../lib/store";

const MAX_PHOTO = 4 * 1024 * 1024;
const uuid = z.string().uuid();

export async function POST(request: Request) {
  try {
    if (!localMediaEnabled(request)) throw new ApiError("Open the local Clip.api portal", 404);
    const { owner, machine } = await identity(request);
    if (machine) throw new ApiError("Only an operator can approve a photo render", 403);
    const form = await boundedForm(request, MAX_PHOTO + 12000);
    const id = uuid.parse(form.get("request_id"));
    const title = z.string().trim().min(3).max(160).parse(form.get("title"));
    const prompt = photoSpec.shape.prompt.parse(form.get("prompt"));
    if (form.get("approved") !== "on") throw new ApiError("Confirm you own the photo and approve the render");
    const photo = form.get("photo");
    if (!(photo instanceof File) || photo.size < 12 || photo.size > MAX_PHOTO)
      throw new ApiError("Choose a JPEG or PNG photo up to 4 MiB");
    const bytes = await photo.arrayBuffer();
    const header = new Uint8Array(bytes);
    const png = [137, 80, 78, 71, 13, 10, 26, 10].every((b, i) => header[i] === b);
    const jpeg = header[0] === 255 && header[1] === 216 && header[2] === 255;
    if (!png && !jpeg) throw new ApiError("Choose a JPEG or PNG photo");
    const mime = png ? "image/png" : "image/jpeg";
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)))
      .map(b => b.toString(16).padStart(2, "0")).join("");
    const seed = 1 + (crypto.getRandomValues(new Uint32Array(1))[0] % 2147483647);
    const recipe = photoSpec.parse({ type: "photo-video", mime, digest, prompt, seed });
    const previous = () => sql(
      "SELECT title,render_spec FROM jobs WHERE owner=? AND id=? AND kind='render'", owner, id,
    ).first<{ title: string; render_spec: string }>();
    function checkReplay(job: Awaited<ReturnType<typeof previous>>) {
      const old = photoSpec.safeParse(JSON.parse(job?.render_spec || "null"));
      if (!job || !old.success || job.title !== title || old.data.digest !== digest || old.data.prompt !== prompt)
        throw new ApiError("This request ID already belongs to a different job", 409);
    }
    const existing = await previous();
    if (existing) {
      checkReplay(existing);
      return response({ id });
    }
    // The digest makes the source immutable even across concurrent form submissions.
    await bucket().put(photoKey(owner, id, digest), bytes, { httpMetadata: { contentType: mime } });
    const timestamp = now();
    const [saved] = await db().batch([
      sql(
        "INSERT OR IGNORE INTO jobs(id,owner,agent,title,brief,lane,mode,kind,status,created,scheduled,approved,render_spec) VALUES(?,?,'ambient-editor',?,?,'ambient','live','render','queued',?,?,1,?)",
        id, owner, title, "Animate the approved original photo on this Mac.", timestamp, timestamp, JSON.stringify(recipe),
      ),
      sql(
        "INSERT INTO events(id,owner,type,message,job,created) SELECT ?,?,'queued',?,?,? WHERE changes()>0",
        crypto.randomUUID(), owner, `Queued local photo-to-video: ${title}`, id, timestamp,
      ),
    ]);
    if (!saved.meta.changes) checkReplay(await previous());
    return response({ id });
  } catch (error) {
    return failure(error);
  }
}

export async function GET(request: Request) {
  try {
    if (!localMediaEnabled(request)) throw new ApiError("Open the local Clip.api portal", 404);
    const { owner, machine, worker } = await identity(request);
    if (!machine || !worker) throw new ApiError("Only the leased worker can read the source photo", 403);
    const id = uuid.parse(request.headers.get("x-render-job"));
    const lease = uuid.parse(request.headers.get("x-render-lease"));
    const { spec } = await renderPreflight(owner, worker, id, lease);
    if (!("type" in spec)) throw new ApiError("No source photo", 404);
    const photo = await bucket().get(photoKey(owner, id, spec.digest));
    if (!photo || photo.size > MAX_PHOTO) throw new ApiError("Source photo unavailable", 404);
    return new Response(photo.body, { headers: { "Content-Type": spec.mime, "Cache-Control": "no-store" } });
  } catch (error) {
    return failure(error);
  }
}
