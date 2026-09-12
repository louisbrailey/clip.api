import { getChatGPTUser } from "../app/chatgpt-auth";
import { initialize, sql } from "./store";
export class ApiError extends Error {
  constructor(
    message: string,
    public status = 400,
  ) {
    super(message);
  }
}
export async function hash(value: string) {
  return Array.from(
    new Uint8Array(
      await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)),
    ),
  )
    .map((x) => x.toString(16).padStart(2, "0"))
    .join("");
}
export async function identity(request: Request) {
  const token = request.headers.get("authorization");
  if (token) {
    if (!/^Bearer cs_[a-f0-9]{64}$/.test(token))
      throw new ApiError("Invalid worker key", 401);
    const user = await sql(
      "SELECT owner FROM settings WHERE worker_hash=?",
      await hash(token.slice(7)),
    ).first<{ owner: string }>();
    if (!user) throw new ApiError("Worker key is invalid or revoked", 401);
    return { owner: user.owner, machine: true };
  }
  const user = await getChatGPTUser();
  if (!user) throw new ApiError("Sign in to your workspace", 401);
  if (
    !["GET", "HEAD"].includes(request.method) &&
    request.headers.get("origin") !== new URL(request.url).origin
  )
    throw new ApiError("Request origin does not match this workspace", 403);
  await initialize(user.userId);
  return { owner: user.userId, machine: false };
}
export function response(body: unknown, status = 200) {
  return Response.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}
export function failure(error: unknown) {
  if (error instanceof ApiError)
    return response({ error: error.message }, error.status);
  if (error && typeof error === "object" && "issues" in error)
    return response(
      { error: "Some fields are invalid. Check required values and limits." },
      400,
    );
  console.error(
    "Control request failed",
    error instanceof Error ? error.name : "unknown",
  );
  return response(
    { error: "The workspace could not save this change. Please retry." },
    503,
  );
}
