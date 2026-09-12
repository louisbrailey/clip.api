import { identity, ApiError, failure, response } from "../../../lib/auth";
import { bucket, db, sql, now, event } from "../../../lib/store";
import { rightsValid } from "../../../lib/domain";
export async function POST(request: Request) {
  try {
    const { owner, machine } = await identity(request);
    if (machine) throw new ApiError("Upload from the content library", 403);
    if (Number(request.headers.get("content-length") || 0) > 52440000)
      throw new ApiError("Media must be smaller than 50 MB", 413);
    const form = await request.formData(),
      file = form.get("file");
    if (!(file instanceof File) || file.size < 12 || file.size > 52428800)
      throw new ApiError("Choose an MP4 video up to 50 MB");
    const header = new Uint8Array(await file.slice(0, 12).arrayBuffer());
    if (String.fromCharCode(...header.slice(4, 8)) !== "ftyp")
      throw new ApiError("The file is not an MP4 container");
    const rights = String(form.get("rights") || ""),
      evidence = String(form.get("evidence") || "").trim();
    const expires = form.get("expires") ? Number(form.get("expires")) : null;
    if (expires !== null && (!Number.isFinite(expires) || expires <= now()))
      throw new ApiError("Enter a future rights-expiry date");
    if (
      evidence.length > 2000 ||
      !rightsValid({ rights, evidence, expires }, now())
    )
      throw new ApiError(
        "Record valid rights and at least 10 characters of evidence",
      );
    const id = crypto.randomUUID(),
      key = `${owner}/${id}.mp4`,
      name = file.name.replace(/[^a-zA-Z0-9._ -]/g, "_").slice(0, 150);
    await bucket().put(key, file.stream(), {
      httpMetadata: { contentType: "video/mp4" },
    });
    try {
      await db().batch([
        sql(
          "INSERT INTO assets(id,owner,name,object_key,mime,size,rights,evidence,expires,created) VALUES(?,?,?,?,?,?,?,?,?,?)",
          id,
          owner,
          name,
          key,
          "video/mp4",
          file.size,
          rights,
          evidence,
          expires,
          now(),
        ),
        event(owner, "media", `Added ${name} with ${rights} rights record`),
      ]);
    } catch (e) {
      await bucket().delete(key);
      throw e;
    }
    return response({ id });
  } catch (e) {
    return failure(e);
  }
}
