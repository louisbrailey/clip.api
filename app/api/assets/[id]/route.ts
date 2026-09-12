import { identity, ApiError, failure } from "../../../../lib/auth";
import { bucket, sql } from "../../../../lib/store";
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { owner } = await identity(request),
      { id } = await params;
    const asset = await sql(
      "SELECT object_key,name,mime FROM assets WHERE owner=? AND id=?",
      owner,
      id,
    ).first<{ object_key: string; name: string; mime: string }>();
    if (!asset) throw new ApiError("Media not found", 404);
    const object = await bucket().get(asset.object_key, {
      range: request.headers,
    });
    if (!object) throw new ApiError("Media unavailable", 404);
    const headers = new Headers({
      "Content-Type": asset.mime,
      "Cache-Control": "private, no-store",
      "Accept-Ranges": "bytes",
      "X-Content-Type-Options": "nosniff",
    });
    if (object.range && "offset" in object.range) {
      const offset = object.range.offset ?? 0,
        length = object.range.length ?? object.size;
      headers.set(
        "Content-Range",
        `bytes ${offset}-${offset + length - 1}/${object.size}`,
      );
      headers.set("Content-Length", String(length));
    } else headers.set("Content-Length", String(object.size));
    return new Response(object.body, {
      status: object.range ? 206 : 200,
      headers,
    });
  } catch (e) {
    return failure(e);
  }
}
