import { identity, ApiError, failure, response } from "../../../lib/auth";
import {
  branch,
  searchAgents,
  readRoutes,
  routeReferences,
  createAgent,
  createAgentInput,
  setRoute,
  routeInput,
  retireAgent,
  updateAgent,
} from "../../../lib/network";
import { agentInput } from "../../../lib/domain";
export const dynamic = "force-dynamic";
export async function GET(request: Request) {
  try {
    const { owner, machine } = await identity(request);
    if (machine)
      throw new ApiError("Worker keys cannot manage agent configurations", 403);
    const q = new URL(request.url).searchParams;
    if (q.has("references"))
      return response(
        await routeReferences(
          owner,
          q.get("references")!,
          q.get("after") || "",
        ),
      );
    if (q.has("routes"))
      return response(
        await readRoutes(owner, q.get("lane") || "", q.get("account")),
      );
    if (q.get("search"))
      return response(
        await searchAgents(owner, q.get("search")!, q.get("after") || ""),
      );
    return response(
      await branch(owner, q.get("focus") || "astra", q.get("after") || ""),
    );
  } catch (e) {
    return failure(e);
  }
}
export async function POST(request: Request) {
  try {
    const { owner, machine } = await identity(request);
    if (machine)
      throw new ApiError(
        "Only the operator can configure agents and routes",
        403,
      );
    const raw = await request.text();
    if (new TextEncoder().encode(raw).length > 40000)
      throw new ApiError("Request too large", 413);
    const body = JSON.parse(raw);
    if (body.action === "create")
      return response(await createAgent(owner, createAgentInput.parse(body)));
    if (body.action === "update")
      await updateAgent(owner, agentInput.parse(body));
    else if (body.action === "retire") await retireAgent(owner, body);
    else if (body.action === "route")
      await setRoute(owner, routeInput.parse(body));
    else throw new ApiError("Unknown agent action");
    return response({ ok: true });
  } catch (e) {
    return failure(e);
  }
}
