/** Optional machine-only entrypoint for a separately provisioned Worker.
 * Build first. Bind the SAME D1/R2 resources as the browser portal.
 * This does not bypass Sites access controls or provision service access.
 */
import application from "../dist/server/index.js";
export default {
  async fetch(request, env, context) {
    const url = new URL(request.url);
    const permitted =
      (url.pathname === "/api/control" && request.method === "POST") ||
      (/^\/api\/assets\/[a-f0-9-]{36}$/.test(url.pathname) &&
        request.method === "GET");
    if (
      !permitted ||
      !/^Bearer cs_[a-f0-9]{64}$/.test(
        request.headers.get("authorization") || "",
      )
    ) {
      return Response.json(
        { error: "Machine authentication required" },
        { status: 401 },
      );
    }
    const headers = new Headers(request.headers);
    for (const key of [...headers.keys()]) {
      if (key.startsWith("oai-authenticated-user-") || key === "cookie")
        headers.delete(key);
    }
    return application.fetch(new Request(request, { headers }), env, context);
  },
};
