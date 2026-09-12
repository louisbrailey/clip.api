"use client";
import { useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  GitBranch,
  Search,
  ArchiveRestore,
  Archive,
  ArrowUp,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import type { Agent, NetworkAgent, NetworkBranch, State } from "@/lib/domain";
import NetworkGraph from "./network-graph";

async function read<T>(path: string): Promise<T> {
  const r = await fetch(path),
    body = (await r.json()) as T & { error?: string };
  if (!r.ok) throw new Error(body.error || "Network unavailable");
  return body;
}
export default function NetworkWorkspace({
  state,
  accountPicker,
  inspector,
  onTasks,
}: {
  state: State;
  accountPicker: (lane: string) => ReactNode;
  inspector: (agent: NetworkAgent, ancestors: Agent[]) => ReactNode;
  onTasks: (id: string) => void;
}) {
  const cache = useQueryClient();
  const [focus, setFocus] = useState("astra"),
    [selected, setSelected] = useState("astra"),
    [pages, setPages] = useState([""]),
    [term, setTerm] = useState(""),
    [searchPages, setSearchPages] = useState([""]),
    [modal, setModal] = useState<"create" | "route" | null>(null),
    [referencePages, setReferencePages] = useState({ agent: "", pages: [""] }),
    [requestId, setRequestId] = useState(""),
    [scope, setScope] = useState("studio"),
    [account, setAccount] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [error, setError] = useState("");
  const after = pages[pages.length - 1],
    searchAfter = searchPages[searchPages.length - 1];
  const query = useQuery<NetworkBranch>({
    queryKey: ["network", focus, after],
    queryFn: () =>
      read(
        `/api/agents?focus=${encodeURIComponent(focus)}&after=${encodeURIComponent(after)}`,
      ),
    refetchInterval: 5000,
    retry: 1,
  });
  const search = useQuery<{ items: NetworkAgent[]; next: string | null }>({
    queryKey: ["agent-search", term, searchAfter],
    queryFn: () =>
      read(
        `/api/agents?search=${encodeURIComponent(term)}&after=${encodeURIComponent(searchAfter)}`,
      ),
    enabled: !!term,
    retry: 1,
  });
  const data = query.data,
    nodes = data ? [data.focus, ...data.children] : [],
    agent = nodes.find((a) => a.id === selected) || data?.focus;
  const routes = useQuery<{
    scope: string;
    routes: {
      role: string;
      agent: string | null;
      agent_name: string | null;
      revision: number;
    }[];
  }>({
    queryKey: ["agent-routes", agent?.lane, scope, account],
    queryFn: () =>
      read(
        `/api/agents?routes=1&lane=${agent!.lane}${scope === "account" ? `&account=${account}` : ""}`,
      ),
    enabled: modal === "route" && !!agent && (scope === "studio" || !!account),
    retry: 1,
  });
  const referenceCursors =
    referencePages.agent === agent?.id ? referencePages.pages : [""];
  const references = useQuery<{
    items: {
      scope: string;
      role: string;
      revision: number;
      handle: string | null;
      platform: string | null;
    }[];
    next: string | null;
  }>({
    queryKey: ["agent-references", agent?.id, referenceCursors.at(-1)],
    queryFn: () =>
      read(
        `/api/agents?references=${agent!.id}&after=${encodeURIComponent(referenceCursors.at(-1)!)}`,
      ),
    enabled: !!agent && agent.route_count > 0,
    retry: 1,
  });
  const route = routes.data?.routes.find((r) => r.role === agent?.task_role);
  function open(id: string) {
    setFocus(id);
    setSelected(id);
    setPages([""]);
    setTerm("");
    setError("");
  }
  async function mutate(body: Record<string, unknown>, success: string) {
    setBusy(true);
    setError("");
    try {
      const r = await fetch("/api/agents", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const value = (await r.json()) as { id: string; error?: string };
      if (!r.ok)
        throw new Error(value.error || "Could not save network change");
      await Promise.all([
        cache.invalidateQueries({ queryKey: ["network"] }),
        cache.invalidateQueries({ queryKey: ["workspace"] }),
        cache.invalidateQueries({ queryKey: ["agent-routes"] }),
        cache.invalidateQueries({ queryKey: ["agent-search"] }),
        cache.invalidateQueries({ queryKey: ["agent-references"] }),
      ]);
      setMessage(success);
      setModal(null);
      if (body.action === "create") open(value.id);
      return true;
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not save network change",
      );
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function assign(reset = false) {
    if (!agent || !routes.data) return;
    await mutate(
      {
        action: "route",
        lane: agent.lane,
        role: agent.task_role,
        account: scope === "account" ? account : null,
        agent: reset ? null : agent.id,
        revision: route?.revision || 0,
      },
      reset
        ? "Routing reset to its default; existing tasks stay assigned"
        : "Future delegated work assigned to this agent",
    );
  }
  return (
    <>
      <div className="panel padded network-search">
        <form
          className="button-row"
          onSubmit={(e) => {
            e.preventDefault();
            setTerm(
              String(new FormData(e.currentTarget).get("term") || "").trim(),
            );
            setSearchPages([""]);
          }}
        >
          <Input
            name="term"
            placeholder="Find agents by name prefix"
            aria-label="Agent name prefix"
            maxLength={80}
          />
          <Button variant="outline" type="submit">
            <Search size={15} /> Find
          </Button>
          {!!term && (
            <Button variant="outline" type="button" onClick={() => setTerm("")}>
              Close search
            </Button>
          )}
          <span className="muted">
            {state.agent_total.toLocaleString()} configurations ·{" "}
            {state.settings.concurrency} concurrent task limit
          </span>
        </form>
        {term && (
          <div className="network-results">
            {search.isPending ? (
              <p>Searching…</p>
            ) : search.isError ? (
              <p role="alert">{search.error.message}</p>
            ) : (
              <>
                {search.data?.items.map((a) => (
                  <Button
                    key={a.id}
                    variant="outline"
                    onClick={() => open(a.id)}
                  >
                    {a.name} · {a.lane} · {a.task_role}
                    {a.archived ? " · retired" : ""}
                  </Button>
                ))}
                {!search.data?.items.length && <p>No matching name prefix.</p>}
                <div className="button-row">
                  <Button
                    variant="outline"
                    disabled={searchPages.length === 1}
                    onClick={() => setSearchPages((p) => p.slice(0, -1))}
                  >
                    Previous matches
                  </Button>
                  <Button
                    variant="outline"
                    disabled={!search.data?.next}
                    onClick={() =>
                      setSearchPages((p) => [...p, search.data!.next!])
                    }
                  >
                    More matches
                  </Button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
      {query.isPending && (
        <div className="loading">
          <Loader2 className="spin" /> Loading network branch…
        </div>
      )}
      {query.isError && (
        <div className="error-panel" role="alert">
          {query.error.message}
          <Button onClick={() => query.refetch()}>Retry</Button>
        </div>
      )}
      {data && agent && (
        <>
          <nav
            className="button-row network-breadcrumb"
            aria-label="Agent ancestry"
          >
            {data.ancestors.map((a) => (
              <Button
                variant="ghost"
                size="sm"
                key={a.id}
                onClick={() => open(a.id)}
              >
                {a.name} /
              </Button>
            ))}
            <strong>{data.focus.name}</strong>
          </nav>
          <div className="network-layout">
            <section className="network-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">THE CONSTELLATION</span>
                  <h2>
                    {data.focus.name}
                    <span className="count-pill">
                      {data.focus.child_count.toLocaleString()} direct children
                    </span>
                  </h2>
                  <p>
                    Open a branch to inspect its agents. Retired configurations
                    remain in history.
                  </p>
                </div>
              </div>
              <NetworkGraph
                agents={nodes}
                counts={Object.fromEntries(
                  nodes.map((a) => [
                    a.id,
                    { running: a.running, queued: a.queued },
                  ]),
                )}
                selected={agent.id}
                onSelect={setSelected}
              />
              <div className="graph-footer button-row">
                <Button
                  variant="outline"
                  disabled={pages.length === 1}
                  onClick={() => setPages((p) => p.slice(0, -1))}
                >
                  Previous children
                </Button>
                <span>Page {pages.length} · up to 12 children</span>
                <Button
                  variant="outline"
                  disabled={!data.next}
                  onClick={() => setPages((p) => [...p, data.next!])}
                >
                  Next children
                </Button>
                {data.focus.parent && (
                  <Button
                    variant="outline"
                    onClick={() => open(data.focus.parent!)}
                  >
                    <ArrowUp size={15} /> Parent
                  </Button>
                )}
              </div>
            </section>
            <div>
              {inspector(agent, [...data.ancestors, ...nodes])}
              <section className="panel padded">
                <div className="button-row">
                  <Button variant="outline" onClick={() => open(agent.id)}>
                    <GitBranch size={15} /> Open branch
                  </Button>
                  <Button variant="outline" onClick={() => onTasks(agent.id)}>
                    View tasks
                  </Button>
                  <Button
                    disabled={
                      busy ||
                      !!agent.archived ||
                      agent.depth < 1 ||
                      agent.depth >= 8
                    }
                    onClick={() => {
                      setError("");
                      setRequestId(crypto.randomUUID());
                      setModal("create");
                    }}
                  >
                    <Plus size={15} /> Add child agent
                  </Button>
                  <Button
                    variant="outline"
                    disabled={
                      busy ||
                      !!agent.archived ||
                      agent.task_role === "orchestrator"
                    }
                    onClick={() => {
                      setError("");
                      setScope("studio");
                      setAccount("");
                      setModal("route");
                    }}
                  >
                    Assign production work
                  </Button>
                  {!agent.core && (
                    <Button
                      variant="outline"
                      disabled={busy}
                      onClick={() =>
                        mutate(
                          {
                            action: "retire",
                            id: agent.id,
                            revision: agent.revision,
                            archived: !agent.archived,
                          },
                          agent.archived
                            ? "Agent restored and kept paused"
                            : "Agent retired; history preserved",
                        )
                      }
                    >
                      {agent.archived ? (
                        <ArchiveRestore size={15} />
                      ) : (
                        <Archive size={15} />
                      )}{" "}
                      {agent.archived ? "Restore" : "Retire"}
                    </Button>
                  )}
                </div>
                <p className="muted">
                  {agent.core
                    ? "Built-in fallback configuration."
                    : agent.route_count
                      ? `${agent.route_count} explicit routing assignment(s).`
                      : "No routing assignments. Assign production work to use this configuration."}{" "}
                  {agent.queued} queued · {agent.running} running.
                </p>
                {agent.route_count > 0 && (
                  <details>
                    <summary>
                      Inspect routing assignments ({agent.route_count})
                    </summary>
                    {references.isPending ? (
                      <p>Loading assignments…</p>
                    ) : references.isError ? (
                      <p role="alert">{references.error.message}</p>
                    ) : (
                      <>
                        {references.data?.items.map((r) => (
                          <div
                            className="button-row"
                            key={r.scope + ":" + r.role}
                          >
                            <span>
                              {r.handle
                                ? `${r.handle} · ${r.platform}`
                                : r.scope}{" "}
                              · {r.role}
                            </span>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={busy}
                              onClick={() =>
                                mutate(
                                  {
                                    action: "route",
                                    lane: agent.lane,
                                    role: r.role,
                                    account: r.scope.startsWith("account:")
                                      ? r.scope.slice(8)
                                      : null,
                                    agent: null,
                                    revision: r.revision,
                                  },
                                  "Assignment reset. Existing tasks retain their assigned agent.",
                                )
                              }
                            >
                              Reset assignment
                            </Button>
                          </div>
                        ))}
                        <div className="button-row">
                          <Button
                            variant="outline"
                            disabled={referenceCursors.length === 1}
                            onClick={() =>
                              setReferencePages({
                                agent: agent.id,
                                pages: referenceCursors.slice(0, -1),
                              })
                            }
                          >
                            Previous assignments
                          </Button>
                          <Button
                            variant="outline"
                            disabled={!references.data?.next}
                            onClick={() =>
                              setReferencePages({
                                agent: agent.id,
                                pages: [
                                  ...referenceCursors,
                                  references.data!.next!,
                                ],
                              })
                            }
                          >
                            More assignments
                          </Button>
                        </div>
                      </>
                    )}
                  </details>
                )}
              </section>
            </div>
          </div>
        </>
      )}
      {(error || message) && (
        <div
          className={error ? "error-panel" : "notice"}
          role={error ? "alert" : "status"}
        >
          {error || message}
        </div>
      )}
      <Dialog
        open={!!modal}
        onOpenChange={(open) => {
          if (!open) setModal(null);
        }}
      >
        <DialogContent className="studio-dialog">
          <DialogHeader>
            <DialogTitle>
              {modal === "create"
                ? "Add an agent configuration"
                : "Assign future production work"}
            </DialogTitle>
            <DialogDescription>
              {modal === "create"
                ? `Reports to ${agent?.name}. Parent, studio and task role stay fixed.`
                : "Astra delegates by role. This choice controls which configured agent receives that work."}
            </DialogDescription>
          </DialogHeader>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          {modal === "create" && agent && (
            <form
              className="form"
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                mutate(
                  {
                    action: "create",
                    request_id: requestId,
                    parent: agent.id,
                    name: f.get("name"),
                    task_role: f.get("task_role"),
                    model: f.get("model"),
                    instructions: f.get("instructions"),
                    concurrency: Number(f.get("concurrency")),
                    paused: f.get("paused") === "on",
                  },
                  "Agent configuration created. Assign a studio or account role to receive work.",
                );
              }}
            >
              <label className="field">
                <span>Agent name</span>
                <Input
                  name="name"
                  minLength={2}
                  maxLength={80}
                  placeholder="Morning meditation writer"
                  required
                />
              </label>
              <div className="form-two">
                <label className="field">
                  <span>Task role</span>
                  <select name="task_role" defaultValue="writer">
                    <option value="lead">Production lead</option>
                    <option value="writer">Writer</option>
                    <option value="editor">Editor</option>
                  </select>
                </label>
                <label className="field">
                  <span>Concurrent tasks</span>
                  <Input
                    type="number"
                    name="concurrency"
                    min={1}
                    max={16}
                    defaultValue={1}
                    required
                  />
                </label>
              </div>
              <label className="field">
                <span>Model</span>
                <Input name="model" defaultValue={agent.model} required />
              </label>
              <label className="field">
                <span>Instructions</span>
                <textarea
                  name="instructions"
                  minLength={1}
                  maxLength={6000}
                  rows={5}
                  placeholder="Audience, tone, production responsibilities and source constraints…"
                  required
                />
              </label>
              <label className="checkbox">
                <input type="checkbox" name="paused" />
                <span>Keep this agent paused</span>
              </label>
              <p className="inset-note">
                Creating a configuration does not start a model call. Your
                workspace execution and token limits still apply.
              </p>
              <Button disabled={busy} type="submit">
                Create agent
              </Button>
            </form>
          )}
          {modal === "route" && agent && (
            <form
              className="form"
              onChange={(e) => {
                const target = e.target as unknown as HTMLSelectElement;
                if (target.name === "account") setAccount(target.value);
              }}
              onSubmit={(e) => {
                e.preventDefault();
                assign();
              }}
            >
              <p>
                <strong>{agent.name}</strong> · {agent.lane} · {agent.task_role}
              </p>
              <label className="field">
                <span>Apply to</span>
                <select
                  value={scope}
                  onChange={(e) => {
                    setScope(e.target.value);
                    setAccount("");
                  }}
                >
                  <option value="studio">This studio’s default role</option>
                  <option value="account">One authorized account</option>
                </select>
              </label>
              {scope === "account" && accountPicker(agent.lane)}
              {routes.isError && (
                <p className="form-error">{routes.error.message}</p>
              )}
              {routes.data && (scope === "studio" || account) && (
                <p className="inset-note">
                  Current assignment:{" "}
                  {route?.agent_name ||
                    (scope === "account"
                      ? "studio default"
                      : "built-in default")}
                  . Existing tasks retain their assigned agent. A paused chosen
                  agent holds future tasks.
                </p>
              )}
              <div className="button-row">
                <Button
                  type="submit"
                  disabled={
                    busy ||
                    routes.isFetching ||
                    !routes.data ||
                    (scope === "account" && !account)
                  }
                >
                  Use {agent.name}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={
                    busy ||
                    routes.isFetching ||
                    !routes.data ||
                    (scope === "account" && !account)
                  }
                  onClick={() => assign(true)}
                >
                  Restore default routing
                </Button>
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
