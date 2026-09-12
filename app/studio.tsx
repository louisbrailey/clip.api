"use client";
import { useState, useRef, type FormEvent, type ReactNode } from "react";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  Activity,
  CalendarClock,
  ArrowDownToLine,
  ArrowUpRight,
  AudioLines,
  Box,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Cpu,
  Download,
  Film,
  Gamepad2,
  GitBranch,
  Layers3,
  ListTodo,
  Loader2,
  Maximize2,
  Minus,
  Network,
  Pause,
  Play,
  Plus,
  Radio,
  RotateCcw,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Target,
  Upload,
  Users,
  X,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  initialAgents,
  lanes,
  platformInfo,
  platforms,
  projectedPoint,
  type Agent,
  type Job,
  type State,
  type Account,
  type Asset,
  type Schedule,
} from "@/lib/domain";

import { SchedulePanel, ScheduleForm } from "./schedules";

const navigation = [
  { id: "network", name: "Orchestration", icon: Network },
  { id: "queue", name: "Work queue", icon: ListTodo },
  { id: "schedules", name: "Schedules", icon: CalendarClock },
  { id: "accounts", name: "Accounts", icon: Users },
  { id: "library", name: "Content library", icon: Film },
  { id: "activity", name: "Activity log", icon: Activity },
  { id: "settings", name: "Controls & setup", icon: Settings2 },
];
const laneName = (value: string) =>
  ({
    originals: "Original studio",
    gaming: "Gaming desk",
    sports: "Sports desk",
    ambient: "Ambient studio",
  })[value] || value;
const pretty = (n: number) =>
  new Intl.NumberFormat("en-US", {
    notation: n >= 10000 ? "compact" : "standard",
    maximumFractionDigits: 1,
  }).format(n);
const when = (n: number) =>
  new Date(n).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
async function request(body: Record<string, unknown>) {
  const r = await fetch("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const v = (await r.json()) as {
    error?: string;
    message?: string;
    token?: string;
    id?: string;
  };
  if (!r.ok) throw new Error(v.error || "Request failed");
  return v;
}
function Badge({ value }: { value: string }) {
  return <span className={`badge ${value.replaceAll(" ", "-")}`}>{value}</span>;
}
function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
function LaneSelect({
  name = "lane",
  defaultValue = "originals",
}: {
  name?: string;
  defaultValue?: string;
}) {
  return (
    <select name={name} defaultValue={defaultValue}>
      {lanes.map((l) => (
        <option key={l} value={l}>
          {laneName(l)}
        </option>
      ))}
    </select>
  );
}
function download(name: string, data: unknown) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(
    new Blob(
      [typeof data === "string" ? data : JSON.stringify(data, null, 2)],
      { type: "application/json" },
    ),
  );
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
export default function Studio({ displayName }: { displayName: string }) {
  const [client] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={client}>
      <ControlRoom displayName={displayName} />
    </QueryClientProvider>
  );
}
function ControlRoom({ displayName }: { displayName: string }) {
  const [tab, setTab] = useState("network"),
    [selected, setSelected] = useState("astra"),
    [modal, setModal] = useState<string | null>(null),
    [job, setJob] = useState<Job | null>(null),
    [schedule, setSchedule] = useState<Schedule | null>(null),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [workerKey, setWorkerKey] = useState(""),
    [offset, setOffset] = useState(0),
    [search, setSearch] = useState("");
  const cache = useQueryClient();
  const query = useQuery<State>({
    queryKey: ["workspace", offset, search],
    queryFn: async () => {
      const r = await fetch(
        `/api/control?offset=${offset}&q=${encodeURIComponent(search)}`,
      );
      const v = (await r.json()) as State & { error?: string };
      if (!r.ok) throw new Error(v.error || "Workspace unavailable");
      return v;
    },
    refetchInterval: 5000,
    retry: 1,
  });
  const s = query.data,
    agents = s?.agents || initialAgents,
    agent = agents.find((a) => a.id === selected) || agents[0];
  async function act(body: Record<string, unknown>, success = "Saved") {
    setBusy(true);
    setError("");
    try {
      const r = await request(body);
      setMessage(r.message || success);
      await cache.invalidateQueries({ queryKey: ["workspace"] });
      return r;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
      return null;
    } finally {
      setBusy(false);
    }
  }
  function navigate(next: string) {
    setTab(next);
    setOffset(0);
    setSearch("");
  }
  async function submit(e: FormEvent<HTMLFormElement>, action: string) {
    e.preventDefault();
    const f = new FormData(e.currentTarget),
      v = Object.fromEntries(f);
    let body: Record<string, unknown> = { action, ...v };
    if (action === "workflow")
      body.scheduled = v.scheduled
        ? new Date(String(v.scheduled)).getTime()
        : Date.now();
    if (action === "schedule") {
      body.interval_minutes = Number(v.interval_minutes);
      body.next_run = new Date(String(v.next_run)).getTime();
      body.max_runs = v.max_runs ? Number(v.max_runs) : null;
      body.paused = f.get("paused") === "on";
      if (v.revision) body.revision = Number(v.revision);
    }
    if (action === "account") {
      body.authorized = f.get("authorized") === "on";
      body.daily_limit = Number(v.daily_limit);
    }
    if (action === "publish") {
      body.approved = f.get("approved") === "on";
      body.scheduled = v.scheduled
        ? new Date(String(v.scheduled)).getTime()
        : Date.now();
    }
    const r = await act(
      body,
      action === "workflow" ? "Workflow added to the queue" : "Saved",
    );
    if (r) {
      setModal(null);
      if (action === "workflow" || action === "publish") navigate("queue");
      if (action === "schedule") navigate("schedules");
    }
  }
  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const f = new FormData(e.currentTarget);
      if (f.get("expires"))
        f.set("expires", String(new Date(String(f.get("expires"))).getTime()));
      const r = await fetch("/api/assets", { method: "POST", body: f });
      const v = (await r.json()) as { error?: string };
      if (!r.ok) throw new Error(v.error || "Upload failed");
      setModal(null);
      setMessage("Media and rights record saved");
      await cache.invalidateQueries({ queryKey: ["workspace"] });
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }
  async function rehearsal() {
    const r = await act(
      {
        action: "workflow",
        title: "A one-minute breathing reset",
        brief:
          "Create an original, calm 60-second breathing meditation with a production brief, an original script and an editorial publishing package.",
        lane: "ambient",
        mode: "rehearsal",
      },
      "Rehearsal queued",
    );
    if (r) {
      navigate("queue");
      setMessage(
        "Rehearsal queued. Use Run next step to inspect each delegation.",
      );
    }
  }
  const workerOnline =
    !!s?.settings.worker_seen && Date.now() - s.settings.worker_seen < 90000;
  const currentJob = job ? s?.jobs.find((j) => j.id === job.id) || job : null;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="/" aria-label="Constellation home">
          <span className="brand-mark">
            <Sparkles size={23} />
          </span>
          <span>
            constellation<span className="brand-sub">CREATIVE OPERATIONS</span>
          </span>
        </a>
        <div className="workspace-switch">
          <span className="avatar">LB</span>
          <div>
            My studio<small>Private workspace</small>
          </div>
          <span className="workspace-arrow">⌄</span>
        </div>
        <p className="nav-caption">CONTROL ROOM</p>
        <nav>
          {navigation.map((item) => (
            <button
              key={item.id}
              className={tab === item.id ? "nav-item selected" : "nav-item"}
              onClick={() => navigate(item.id)}
            >
              <item.icon size={18} />
              <span>{item.name}</span>
              {item.id === "queue" && !!s?.counts.queued && (
                <em>{s.counts.queued}</em>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="worker-health">
            <Radio size={17} />
            <span>
              {workerOnline ? "Worker connected" : "Worker offline"}
              <small>
                {workerOnline
                  ? "Heartbeat received"
                  : "Connect in Controls & setup"}
              </small>
            </span>
          </div>
          <button className="help-link" onClick={() => navigate("settings")}>
            <CircleHelp size={16} /> Setup & operating limits
            <ArrowUpRight size={14} />
          </button>
          <div className="profile">
            <span className="profile-initial">
              {displayName[0]?.toUpperCase()}
            </span>
            <div title={displayName}>
              {displayName}
              <small>Workspace owner</small>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            My studio <span>/</span>{" "}
            <strong>{navigation.find((n) => n.id === tab)?.name}</strong>
          </div>
          <div className="top-meta">
            <ShieldCheck size={15} />
            <span>Private</span>
            <span className="divider" />
            <span className="mono">
              UTC{new Date().getTimezoneOffset() > 0 ? "−" : "+"}
              {Math.abs(new Date().getTimezoneOffset() / 60)}
            </span>
          </div>
        </header>
        <main className="workspace-main">
          <div className="page-heading">
            <div>
              <div className="eyebrow">YOUR STUDIO, CONNECTED</div>
              <h1>{navigation.find((n) => n.id === tab)?.name}</h1>
              <p>
                {tab === "network"
                  ? "Direct the work. Follow every delegation."
                  : tab === "queue"
                    ? "From a single brief to a complete publishing package."
                    : tab === "schedules"
                      ? "Give every account a steady production rhythm."
                      : tab === "accounts"
                        ? "A registry for accounts you own or are authorized to manage."
                        : tab === "library"
                          ? "Source media and the rights behind every publication."
                          : tab === "activity"
                            ? "A durable record of work, decisions and controls."
                            : "Set the limits. Connect the runtime. Keep control."}
              </p>
            </div>
            <div className="heading-actions">
              {s && (
                <Button
                  variant="outline"
                  className={s.settings.paused ? "resume-button" : ""}
                  disabled={busy}
                  onClick={() =>
                    act(
                      {
                        action: "settings",
                        ...s.settings,
                        paused: !s.settings.paused,
                      },
                      s.settings.paused
                        ? "Dispatch resumed"
                        : "Dispatch paused; current calls may finish",
                    )
                  }
                >
                  {s.settings.paused ? <Play size={15} /> : <Pause size={15} />}{" "}
                  {s.settings.paused ? "Resume studio" : "Pause studio"}
                </Button>
              )}
              <Button
                disabled={!s || busy}
                onClick={() => {
                  setSchedule(null);
                  setModal(
                    tab === "schedules"
                      ? "schedule"
                      : tab === "accounts"
                        ? "account"
                        : tab === "library"
                          ? "upload"
                          : "workflow",
                  );
                }}
              >
                <Plus size={16} />
                {tab === "schedules"
                  ? "New schedule"
                  : tab === "accounts"
                    ? "Register account"
                    : tab === "library"
                      ? "Add media"
                      : "New workflow"}
              </Button>
            </div>
          </div>
          {query.isError && (
            <div className="error-panel" role="alert">
              <strong>Workspace unavailable</strong>
              <p>{query.error.message}</p>
              <Button variant="outline" onClick={() => query.refetch()}>
                Retry connection
              </Button>
            </div>
          )}
          {!s && !query.isError && (
            <div className="loading">
              <Loader2 className="spin" /> Loading your workspace…
            </div>
          )}
          {s && (
            <>
              <section
                className="metrics"
                aria-label="Current workspace metrics"
              >
                {[
                  {
                    label: "REGISTERED ACCOUNTS",
                    value: s.account_total,
                    icon: Users,
                    detail: "10,000 registry capacity",
                  },
                  {
                    label: "QUEUED TASKS",
                    value: s.counts.queued || 0,
                    icon: Layers3,
                    detail: `${s.counts.succeeded || 0} completed · includes rehearsals`,
                  },
                  {
                    label: "RUNNING TASKS",
                    value: s.counts.running || 0,
                    icon: Cpu,
                    detail: `${s.settings.concurrency} concurrent task limit`,
                  },
                  {
                    label: "TOKEN BUDGET CHARGED",
                    value: s.tokens_today,
                    icon: Zap,
                    detail: `${pretty(s.settings.daily_tokens)} daily limit · ${pretty(s.reserved_today)} reserved`,
                  },
                ].map((m) => (
                  <div className="metric" key={m.label}>
                    <div className="metric-label">
                      {m.label}
                      <m.icon size={16} />
                    </div>
                    <div className="metric-value">{pretty(m.value)}</div>
                    <div className="metric-detail">{m.detail}</div>
                  </div>
                ))}
              </section>
              {s.settings.paused === 1 && (
                <div className="notice">
                  <Pause size={17} />
                  <span>
                    Studio paused. New dispatch is stopped; calls already
                    accepted by providers may finish.
                  </span>
                </div>
              )}
              {tab === "network" && (
                <>
                  <div className="network-layout">
                    <section className="network-panel">
                      <div className="panel-heading">
                        <div>
                          <span className="eyebrow">THE CONSTELLATION</span>
                          <h2>
                            Delegation network{" "}
                            <span className="count-pill">
                              {agents.length} agents
                            </span>
                          </h2>
                        </div>
                        <Badge
                          value={
                            workerOnline ? "worker connected" : "configured"
                          }
                        />
                      </div>
                      <NetworkGraph
                        agents={agents}
                        counts={s.agent_counts}
                        selected={selected}
                        onSelect={setSelected}
                      />
                      <div className="graph-footer">
                        <span>
                          <i style={{ background: "var(--lime)" }} />{" "}
                          Orchestrator
                        </span>
                        <span>
                          <i style={{ background: "#7ea5ff" }} /> Studio lead
                        </span>
                        <span>
                          <i style={{ background: "#9cabbc" }} /> Worker
                        </span>
                        <span className="graph-hint">
                          Select an agent to direct its work
                        </span>
                      </div>
                    </section>
                    <AgentInspector
                      key={
                        agent.id +
                        agent.model +
                        agent.instructions +
                        agent.paused +
                        agent.concurrency
                      }
                      agent={agent}
                      agents={agents}
                      running={s.agent_counts[agent.id]?.running || 0}
                      busy={busy}
                      act={act}
                    />
                  </div>
                  <div className="studio-grid">
                    {lanes.map((l, i) => {
                      const a = agents.find((a) => a.id === l)!;
                      const Icon = [Sparkles, Gamepad2, Target, AudioLines][i];
                      return (
                        <button
                          className="studio-card"
                          key={l}
                          onClick={() => setSelected(l)}
                        >
                          <div
                            className="studio-icon"
                            style={{ color: a.color }}
                          >
                            <Icon size={21} />
                          </div>
                          <div>
                            <h3>{a.name}</h3>
                            <p>{a.role}</p>
                            <span>
                              {s.lane_counts[l]?.queued || 0} queued tasks
                            </span>
                          </div>
                          <ArrowUpRight size={16} />
                        </button>
                      );
                    })}
                  </div>
                  <div className="rehearsal-strip">
                    <div className="rehearsal-symbol">
                      <GitBranch size={24} />
                    </div>
                    <div>
                      <h3>Take your first workflow for a test run.</h3>
                      <p>
                        Trace a brief through Astra and the Ambient studio.
                        Rehearsals use no API credits and publish nothing.
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      disabled={busy}
                      onClick={rehearsal}
                    >
                      <Play size={15} /> Try a rehearsal
                    </Button>
                  </div>
                </>
              )}
              {tab === "queue" && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>
                        All work{" "}
                        <span className="count-pill">{s.job_total}</span>
                      </h2>
                      <p>
                        Rehearsal tasks are deterministic examples. Live tasks
                        need a connected worker.
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      disabled={busy}
                      onClick={() =>
                        act({ action: "rehearse" }, "Rehearsal step completed")
                      }
                    >
                      <Play size={15} /> Run next rehearsal step
                    </Button>
                  </div>
                  <SearchBar
                    key={tab}
                    onSearch={(v) => {
                      setSearch(v);
                      setOffset(0);
                    }}
                  />
                  {s.jobs.length ? (
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Task / workflow</th>
                            <th>Agent</th>
                            <th>Mode</th>
                            <th>Status</th>
                            <th>Scheduled</th>
                            <th />
                          </tr>
                        </thead>
                        <tbody>
                          {s.jobs.map((j) => (
                            <tr key={j.id} onClick={() => setJob(j)}>
                              <td>
                                <button
                                  className="table-task"
                                  onClick={() => setJob(j)}
                                >
                                  {j.parent && <GitBranch size={15} />}
                                  <span>
                                    {j.title}
                                    <small>
                                      {laneName(j.lane)} · {j.kind}
                                    </small>
                                  </span>
                                </button>
                              </td>
                              <td className="mono">{j.agent}</td>
                              <td>
                                <Badge value={j.mode} />
                              </td>
                              <td>
                                <Badge value={j.status} />
                              </td>
                              <td className="table-date">
                                {when(j.scheduled)}
                              </td>
                              <td>
                                <ChevronRight size={15} />
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <Empty
                      icon={<GitBranch />}
                      title="A clear runway"
                      text="Create a workflow and Astra will delegate its production steps."
                      action={
                        <Button onClick={() => setModal("workflow")}>
                          <Plus size={15} /> New workflow
                        </Button>
                      }
                    />
                  )}
                  <Pagination
                    offset={offset}
                    total={
                      search
                        ? offset +
                          s.jobs.length +
                          (s.jobs.length === 60 ? 1 : 0)
                        : s.job_total
                    }
                    setOffset={setOffset}
                  />
                </section>
              )}
              {tab === "schedules" && (
                <SchedulePanel
                  state={s}
                  busy={busy}
                  offset={offset}
                  search={search}
                  onSearch={(v) => {
                    setSearch(v);
                    setOffset(0);
                  }}
                  onPage={setOffset}
                  act={act}
                  onEdit={(v) => {
                    setSchedule(v);
                    setModal("schedule");
                  }}
                  onRun={(id) => {
                    navigate("queue");
                    setSearch(id);
                  }}
                />
              )}
              {tab === "accounts" && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>
                        Account registry{" "}
                        <span className="count-pill">{s.account_total}</span>
                      </h2>
                      <p>
                        Registration records authorization; it does not connect
                        or verify OAuth credentials.
                      </p>
                    </div>
                  </div>
                  <div className="platform-strip">
                    {platforms.map((p) => (
                      <span key={p}>
                        {platformInfo[p].name}
                        <small>{platformInfo[p].support}</small>
                      </span>
                    ))}
                  </div>
                  <SearchBar
                    key={tab}
                    onSearch={(v) => {
                      setSearch(v);
                      setOffset(0);
                    }}
                  />
                  {s.accounts.length ? (
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Account</th>
                            <th>Studio</th>
                            <th>Integration</th>
                            <th>Daily cap</th>
                            <th>Dispatch</th>
                          </tr>
                        </thead>
                        <tbody>
                          {s.accounts.map((a) => (
                            <tr key={a.id}>
                              <td>
                                <strong>{a.handle}</strong>
                                <small>
                                  {platformInfo[a.platform].name} ·{" "}
                                  {a.external_id}
                                </small>
                              </td>
                              <td>{laneName(a.lane)}</td>
                              <td>
                                <Badge
                                  value={platformInfo[a.platform].support}
                                />
                                <small className="mono">
                                  {a.credential_ref}
                                </small>
                              </td>
                              <td>{a.daily_limit} uploads</td>
                              <td>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  disabled={busy}
                                  onClick={() =>
                                    act({
                                      action: "account-pause",
                                      id: a.id,
                                      paused: !a.paused,
                                    })
                                  }
                                >
                                  {a.paused ? <Play /> : <Pause />}
                                  {a.paused ? "Resume" : "Pause"}
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <Empty
                      icon={<Users />}
                      title="Your accounts start here"
                      text="Register an authorized account, then configure its OAuth credentials on your worker."
                      action={
                        <Button onClick={() => setModal("account")}>
                          <Plus size={15} /> Register account
                        </Button>
                      }
                    />
                  )}
                  <Pagination
                    offset={offset}
                    total={
                      search
                        ? offset +
                          s.accounts.length +
                          (s.accounts.length === 60 ? 1 : 0)
                        : s.account_total
                    }
                    setOffset={setOffset}
                  />
                </section>
              )}
              {tab === "library" && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>
                        Source media{" "}
                        <span className="count-pill">{s.asset_total}</span>
                      </h2>
                      <p>
                        MP4 files up to 50 MB. Original work, licensed content
                        or verified public-domain material.
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      disabled={!s.assets.length || !s.account_total}
                      onClick={() => setModal("publish")}
                    >
                      <ArrowUpRight size={15} /> Schedule private upload
                    </Button>
                  </div>
                  <SearchBar
                    key={tab}
                    onSearch={(v) => {
                      setSearch(v);
                      setOffset(0);
                    }}
                  />
                  {s.assets.length ? (
                    <div className="asset-grid">
                      {s.assets.map((a) => (
                        <article className="asset-card" key={a.id}>
                          <video
                            controls
                            preload="metadata"
                            src={`/api/assets/${a.id}`}
                            aria-label={a.name}
                          />
                          <div className="asset-info">
                            <h3>{a.name}</h3>
                            <div className="asset-meta">
                              <Badge value={a.rights} />
                              <span>{(a.size / 1048576).toFixed(1)} MB</span>
                            </div>
                            <p>{a.evidence}</p>
                            <small>
                              {a.expires
                                ? `Rights expire ${when(a.expires)}`
                                : "No recorded expiry"}
                            </small>
                            <div className="asset-actions">
                              <a href={`/api/assets/${a.id}`} download={a.name}>
                                <Download size={15} /> Media
                              </a>
                              <button
                                onClick={() =>
                                  download(`${a.name}.rights.json`, {
                                    name: a.name,
                                    rights: a.rights,
                                    evidence: a.evidence,
                                    expires: a.expires,
                                    asset_id: a.id,
                                  })
                                }
                              >
                                <ArrowDownToLine size={15} /> Rights record
                              </button>
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <Empty
                      icon={<Film />}
                      title="Give your studio something to work with"
                      text="Upload source media and record its provenance. A bundled local renderer can also create original ambient videos."
                      action={
                        <Button onClick={() => setModal("upload")}>
                          <Upload size={15} /> Add media
                        </Button>
                      }
                    />
                  )}
                  <Pagination
                    offset={offset}
                    total={
                      search
                        ? offset +
                          s.assets.length +
                          (s.assets.length === 60 ? 1 : 0)
                        : s.asset_total
                    }
                    setOffset={setOffset}
                  />
                </section>
              )}
              {tab === "activity" && (
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Activity stream</h2>
                      <p>Most recent 100 workspace events.</p>
                    </div>
                    <Button
                      variant="outline"
                      onClick={() =>
                        download("constellation-activity.json", s.events)
                      }
                    >
                      <Download size={15} /> Export log
                    </Button>
                  </div>
                  {s.events.length ? (
                    <div className="event-list">
                      {s.events.map((e) => (
                        <div className="event" key={e.id}>
                          <span className="event-mark">
                            <Activity size={16} />
                          </span>
                          <div>
                            <strong>{e.message}</strong>
                            <small>{e.job || "Workspace"}</small>
                          </div>
                          <Badge value={e.type} />
                          <time>{when(e.created)}</time>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Empty
                      icon={<Activity />}
                      title="No activity yet"
                      text="The first workflow or control change will appear here."
                    />
                  )}
                </section>
              )}
              {tab === "settings" && (
                <div className="settings-grid">
                  <section className="panel padded">
                    <div className="section-icon">
                      <Settings2 />
                    </div>
                    <h2>Execution limits</h2>
                    <p className="muted">
                      Limits are enforced when claiming each job. Model calls
                      already in flight can finish.
                    </p>
                    <form
                      className="form"
                      onSubmit={async (e) => {
                        e.preventDefault();
                        const f = new FormData(e.currentTarget);
                        await act({
                          action: "settings",
                          paused: !!s.settings.paused,
                          concurrency: Number(f.get("concurrency")),
                          daily_tokens: Number(f.get("daily_tokens")),
                        });
                      }}
                    >
                      <Field
                        label="Concurrent task limit"
                        hint="1–32 active tasks across this workspace"
                      >
                        <Input
                          name="concurrency"
                          type="number"
                          min={1}
                          max={32}
                          defaultValue={s.settings.concurrency}
                          required
                        />
                      </Field>
                      <Field
                        label="Daily token allowance (UTC)"
                        hint="Each live model call reserves 20,000 tokens. Unknown outcomes retain this charge. Token allowances are not dollar spending limits."
                      >
                        <Input
                          name="daily_tokens"
                          type="number"
                          min={20000}
                          max={10000000}
                          defaultValue={s.settings.daily_tokens}
                          required
                        />
                      </Field>
                      <Button disabled={busy}>Save limits</Button>
                    </form>
                    <div className="inset-note">
                      This release supports at most 32 concurrent tasks per
                      workspace. Million-job throughput and 10,000 active
                      platform connections have not been load-tested.
                    </div>
                  </section>
                  <section className="panel padded">
                    <div className="section-icon">
                      <Cpu />
                    </div>
                    <h2>Connect a worker</h2>
                    <p className="muted">
                      Run the included Python worker on an always-on machine.
                      Credentials stay in that runtime, outside the portal.
                    </p>
                    <ol className="setup-steps">
                      <li>
                        <span>01</span>
                        <div>
                          <strong>Configure model access</strong>
                          <p>
                            Set OPENAI_API_KEY for gpt-6-astra and the selected
                            worker models.
                          </p>
                        </div>
                      </li>
                      <li>
                        <span>02</span>
                        <div>
                          <strong>Create a worker key</strong>
                          <p>
                            The key is shown once. Rotating it revokes the
                            previous key.
                          </p>
                        </div>
                      </li>
                      <li>
                        <span>03</span>
                        <div>
                          <strong>Start the supervised runtime</strong>
                          <p>
                            Use the Docker deployment in the source deliverable.
                            Configure SITES_API_TOKEN for this portal alongside
                            your worker key, then start the worker on an
                            always-on host.
                          </p>
                        </div>
                      </li>
                    </ol>
                    <div className="button-row">
                      <Button
                        disabled={busy}
                        onClick={async () => {
                          const r = await act(
                            { action: "worker-key" },
                            "Worker key created",
                          );
                          if (r?.token) setWorkerKey(r.token);
                        }}
                      >
                        {s.settings.has_worker_key
                          ? "Rotate worker key"
                          : "Create worker key"}
                      </Button>
                      {s.settings.has_worker_key && (
                        <Button
                          variant="outline"
                          disabled={busy}
                          onClick={async () => {
                            await act(
                              { action: "revoke-key" },
                              "Worker key revoked",
                            );
                            setWorkerKey("");
                          }}
                        >
                          Revoke key
                        </Button>
                      )}
                    </div>
                    {workerKey && (
                      <div className="key-box">
                        <p>
                          Copy this key to your worker environment. It will
                          disappear when you leave the page.
                        </p>
                        <code>{workerKey}</code>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={async () => {
                            try {
                              await navigator.clipboard.writeText(workerKey);
                              setMessage("Worker key copied");
                            } catch {
                              setError(
                                "Clipboard unavailable. Select and copy the key.",
                              );
                            }
                          }}
                        >
                          Copy key
                        </Button>
                      </div>
                    )}
                    <div className="worker-status">
                      <Radio size={15} />
                      {workerOnline
                        ? `Last heartbeat ${when(s.settings.worker_seen!)}`
                        : "No recent worker heartbeat"}
                    </div>
                  </section>
                  <section className="panel padded span-two">
                    <h2>Publishing availability</h2>
                    <div className="integration-grid">
                      {platforms.map((p) => (
                        <div key={p}>
                          <div className="integration-title">
                            <strong>{platformInfo[p].name}</strong>
                            <Badge value={platformInfo[p].support} />
                          </div>
                          <p>{platformInfo[p].note}</p>
                          <a
                            href={platformInfo[p].url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Platform documentation <ArrowUpRight size={13} />
                          </a>
                        </div>
                      ))}
                    </div>
                  </section>
                </div>
              )}
              <footer className="workspace-footer">
                <span>
                  <span className="tiny-star">✳</span> CONSTELLATION
                </span>
                <span>Astra orchestrates. You direct.</span>
                <span>Original & authorized content only</span>
              </footer>
            </>
          )}
        </main>
      </div>
      {(message || error) && (
        <div
          className={`toast ${error ? "toast-error" : ""}`}
          role={error ? "alert" : "status"}
        >
          {error ? <CircleHelp size={17} /> : <Check size={17} />}
          <span>{error || message}</span>
          <button
            aria-label="Dismiss notification"
            onClick={() => {
              setError("");
              setMessage("");
            }}
          >
            <X size={16} />
          </button>
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
              {modal === "schedule"
                ? schedule
                  ? "Edit recurring workflow"
                  : "Create a recurring workflow"
                : modal === "workflow"
                  ? "Start a workflow"
                  : modal === "account"
                    ? "Register an authorized account"
                    : modal === "upload"
                      ? "Add source media"
                      : "Schedule a private YouTube upload"}
            </DialogTitle>
            <DialogDescription>
              {modal === "schedule"
                ? "Set the creative direction and timing for one authorized account."
                : modal === "workflow"
                  ? "Astra turns your brief into a bounded sequence of studio tasks."
                  : modal === "account"
                    ? "This records your account. Configure credentials separately on the worker."
                    : modal === "upload"
                      ? "Attach the source video and record your right to publish it."
                      : "Review the exact title, description, account and source before approving the upload."}
            </DialogDescription>
          </DialogHeader>
          {modal === "schedule" && (
            <ScheduleForm
              value={schedule}
              busy={busy}
              onSubmit={(e) => submit(e, "schedule")}
            >
              <AccountPicker purpose="production" />
            </ScheduleForm>
          )}
          {modal === "workflow" && (
            <form className="form" onSubmit={(e) => submit(e, "workflow")}>
              <Field label="Workflow title">
                <Input
                  name="title"
                  placeholder="A one-minute breathing reset"
                  minLength={3}
                  maxLength={160}
                  required
                />
              </Field>
              <Field label="Studio">
                <LaneSelect />
              </Field>
              <Field label="Production brief">
                <textarea
                  name="brief"
                  placeholder="Describe the audience, creative direction, source material and desired output…"
                  minLength={15}
                  maxLength={6000}
                  rows={5}
                  required
                />
              </Field>
              <div className="form-two">
                <Field label="Execution">
                  <select name="mode">
                    <option value="rehearsal">
                      Rehearsal · no model calls
                    </option>
                    <option value="live">
                      Live · connected worker required
                    </option>
                  </select>
                </Field>
                <Field label="Start time (local, optional)">
                  <Input type="datetime-local" name="scheduled" />
                </Field>
              </div>
              <p className="inset-note">
                Workflows produce briefs, scripts and editorial packages. Video
                rendering and publication are separate, visible steps.
              </p>
              <Button disabled={busy} type="submit">
                {busy ? <Loader2 className="spin" /> : <GitBranch size={16} />}{" "}
                Queue workflow
              </Button>
            </form>
          )}
          {modal === "account" && (
            <form className="form" onSubmit={(e) => submit(e, "account")}>
              <div className="form-two">
                <Field label="Platform">
                  <select name="platform">
                    {platforms.map((p) => (
                      <option key={p} value={p}>
                        {platformInfo[p].name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Studio">
                  <LaneSelect />
                </Field>
              </div>
              <Field label="Account handle">
                <Input
                  name="handle"
                  placeholder="@yourstudio"
                  minLength={2}
                  maxLength={100}
                  required
                />
              </Field>
              <Field label="Platform account / channel ID">
                <Input
                  name="external_id"
                  placeholder="Your authorized channel ID"
                  maxLength={120}
                  required
                />
              </Field>
              <Field
                label="Worker credential reference"
                hint="Environment-variable name only. Do not enter a token or password."
              >
                <Input
                  name="credential_ref"
                  pattern="[A-Z][A-Z0-9_]{2,79}"
                  placeholder="YOUTUBE_AMBIENT"
                  required
                />
              </Field>
              <Field label="Daily upload cap">
                <Input
                  type="number"
                  name="daily_limit"
                  min={1}
                  max={100}
                  defaultValue={1}
                  required
                />
              </Field>
              <label className="checkbox">
                <input type="checkbox" name="authorized" required />
                <span>
                  I own this account or have explicit authorization to manage
                  it.
                </span>
              </label>
              <Button type="submit" disabled={busy}>
                Register account
              </Button>
            </form>
          )}
          {modal === "upload" && (
            <form className="form" onSubmit={upload}>
              <Field label="MP4 source video">
                <Input
                  type="file"
                  name="file"
                  accept="video/mp4,.mp4"
                  required
                />
              </Field>
              <Field label="Content rights">
                <select name="rights">
                  <option value="original">Original work I own</option>
                  <option value="licensed">Licensed for this use</option>
                  <option value="public-domain">Verified public domain</option>
                </select>
              </Field>
              <Field
                label="Rights evidence"
                hint="Record source, creator, permission or license reference, and permitted use."
              >
                <textarea
                  name="evidence"
                  minLength={10}
                  maxLength={2000}
                  rows={4}
                  required
                />
              </Field>
              <Field label="Rights expiry (optional)">
                <Input type="date" name="expires" />
              </Field>
              <Button disabled={busy} type="submit">
                {busy ? <Loader2 className="spin" /> : <Upload size={16} />}{" "}
                Upload & save rights
              </Button>
            </form>
          )}
          {modal === "publish" && s && (
            <form className="form" onSubmit={(e) => submit(e, "publish")}>
              <AccountPicker />
              <Field label="Approved source media">
                <select name="asset" required>
                  <option value="">Select a video</option>
                  {s.assets.map((a) => (
                    <option value={a.id} key={a.id}>
                      {a.name} · {a.rights}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Exact video title">
                <Input name="title" minLength={3} maxLength={100} required />
              </Field>
              <Field label="Exact description">
                <textarea
                  name="brief"
                  minLength={1}
                  maxLength={4500}
                  required
                  rows={4}
                />
              </Field>
              <Field label="Upload time (local, optional)">
                <Input type="datetime-local" name="scheduled" />
              </Field>
              <div className="inset-note">
                Visibility: private. Review the result in YouTube Studio before
                making it public. Account OAuth must match the registered
                channel ID.
              </div>
              <label className="checkbox">
                <input type="checkbox" name="approved" required />
                <span>
                  I approve this exact private upload and confirm the source
                  rights cover this account and use.
                </span>
              </label>
              <Button type="submit" disabled={busy}>
                Approve & schedule upload
              </Button>
            </form>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
        </DialogContent>
      </Dialog>
      <Dialog
        open={!!currentJob}
        onOpenChange={(open) => {
          if (!open) setJob(null);
        }}
      >
        <DialogContent className="studio-dialog job-dialog">
          <DialogHeader>
            <DialogTitle>{currentJob?.title}</DialogTitle>
            <DialogDescription>
              Task details, delegation and output
            </DialogDescription>
          </DialogHeader>
          {currentJob && (
            <>
              <div className="button-row">
                <Badge value={currentJob.status} />
                <Badge value={currentJob.mode} />
                <span className="mono">{currentJob.agent}</span>
              </div>
              <div className="job-details">
                <span>
                  Task ID <code>{currentJob.id}</code>
                </span>
                {currentJob.parent && (
                  <span>
                    Parent <code>{currentJob.parent}</code>
                  </span>
                )}
                {currentJob.schedule_id && (
                  <span>
                    Recurring schedule <code>{currentJob.schedule_id}</code> ·{" "}
                    {when(currentJob.occurrence!)}
                  </span>
                )}
                <span>
                  Attempts <b>{currentJob.attempts}/3</b>
                </span>
              </div>
              <h3>Brief</h3>
              <p className="pre-line">{currentJob.brief}</p>
              {currentJob.result && (
                <>
                  <h3>Output</h3>
                  <pre className="result-output">{currentJob.result}</pre>
                  <Button
                    variant="outline"
                    onClick={() =>
                      download(`${currentJob.id}.json`, {
                        ...currentJob,
                        lease: undefined,
                      })
                    }
                  >
                    <Download size={15} /> Export task & output
                  </Button>
                </>
              )}
              {currentJob.receipt && (
                <div className="inset-note">
                  Provider receipt: {currentJob.receipt}
                </div>
              )}
              {currentJob.error && (
                <p className="form-error">{currentJob.error}</p>
              )}
              <div className="button-row">
                {["queued", "blocked", "failed"].includes(
                  currentJob.status,
                ) && (
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() =>
                      act(
                        { action: "cancel", id: currentJob.id },
                        "Task cancelled",
                      )
                    }
                  >
                    Cancel task
                  </Button>
                )}
                {currentJob.status === "failed" &&
                  currentJob.kind !== "publish" &&
                  currentJob.attempts < 3 && (
                    <Button
                      disabled={busy}
                      onClick={() =>
                        act(
                          { action: "retry", id: currentJob.id },
                          "Task queued",
                        )
                      }
                    >
                      Retry task
                    </Button>
                  )}
              </div>
              {currentJob.status === "uncertain" && (
                <form
                  className="form"
                  onSubmit={async (e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    await act(
                      {
                        action: "reconcile",
                        id: currentJob.id,
                        receipt: f.get("receipt"),
                      },
                      "Receipt recorded",
                    );
                  }}
                >
                  <Field
                    label="Verified YouTube video ID or URL"
                    hint="Check YouTube Studio first. Uncertain uploads are never retried automatically."
                  >
                    <Input
                      name="receipt"
                      minLength={3}
                      maxLength={500}
                      required
                    />
                  </Field>
                  <Button disabled={busy}>Record verified receipt</Button>
                </form>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
function SearchBar({ onSearch }: { onSearch: (s: string) => void }) {
  return (
    <form
      className="searchbar"
      onSubmit={(e) => {
        e.preventDefault();
        onSearch(String(new FormData(e.currentTarget).get("q") || ""));
      }}
    >
      <Search size={17} />
      <input
        aria-label="Search by name or ID"
        name="q"
        placeholder="Search by name or ID…"
        maxLength={120}
      />
      <Button variant="ghost" size="sm" type="submit">
        Search
      </Button>
      <Button
        variant="ghost"
        size="sm"
        type="reset"
        onClick={() => onSearch("")}
      >
        Clear
      </Button>
    </form>
  );
}
function Pagination({
  offset,
  total,
  setOffset,
}: {
  offset: number;
  total: number;
  setOffset: (n: number) => void;
}) {
  return (
    <div className="pagination">
      <span>
        {total
          ? `${offset + 1}–${Math.min(offset + 60, total)} of ${total}`
          : "0 records"}
      </span>
      <Button
        variant="outline"
        size="sm"
        aria-label="Previous page"
        disabled={!offset}
        onClick={() => setOffset(Math.max(0, offset - 60))}
      >
        <ChevronLeft />
      </Button>
      <Button
        variant="outline"
        size="sm"
        aria-label="Next page"
        disabled={offset + 60 >= total}
        onClick={() => setOffset(offset + 60)}
      >
        <ChevronRight />
      </Button>
    </div>
  );
}
function Empty({
  icon,
  title,
  text,
  action,
}: {
  icon: ReactNode;
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">{icon}</span>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
function AgentInspector({
  agent,
  agents,
  running,
  busy,
  act,
}: {
  agent: Agent;
  agents: Agent[];
  running: number;
  busy: boolean;
  act: (v: Record<string, unknown>, s?: string) => Promise<unknown>;
}) {
  const ancestorPaused = agents.some(
    (a) =>
      (a.id === agent.parent || a.id === "astra") &&
      a.id !== agent.id &&
      a.paused,
  );
  return (
    <aside className="inspector">
      <div className="inspector-top">
        <span className="eyebrow">AGENT INSPECTOR</span>
        <span className="mono">{agent.id === "astra" ? "01" : "↳"}</span>
      </div>
      <div className="agent-avatar" style={{ color: agent.color }}>
        {agent.id === "astra" ? <Sparkles size={29} /> : <Cpu size={27} />}
      </div>
      <h2>{agent.name}</h2>
      <p className="muted">{agent.role}</p>
      <div className="agent-tags">
        <Badge
          value={
            agent.paused
              ? "paused"
              : ancestorPaused
                ? "parent paused"
                : "enabled"
          }
        />
        <span>
          {agent.parent ? `Reports to ${agent.parent}` : "Network root"}
        </span>
      </div>
      <div className="agent-divider" />
      <form
        className="form"
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          act(
            {
              action: "agent",
              id: agent.id,
              paused: !!agent.paused,
              model: f.get("model"),
              concurrency: Number(f.get("concurrency")),
              instructions: f.get("instructions"),
            },
            "Agent configuration saved",
          );
        }}
      >
        <Field label="Assigned model">
          <Input
            className="mono"
            name="model"
            defaultValue={agent.model}
            readOnly={agent.id === "astra"}
            required
          />
        </Field>
        <Field label="Concurrent tasks for this agent">
          <Input
            name="concurrency"
            type="number"
            min={1}
            max={16}
            defaultValue={agent.concurrency}
            required
          />
        </Field>
        <Field label="Agent instructions">
          <textarea
            name="instructions"
            rows={4}
            maxLength={6000}
            defaultValue={agent.instructions}
            required
          />
        </Field>
        <div className="button-row">
          <Button disabled={busy} type="submit">
            Save changes
          </Button>
          <Button
            disabled={busy}
            type="button"
            variant="outline"
            aria-label={agent.paused ? "Resume agent" : "Pause agent"}
            onClick={() =>
              act(
                { action: "agent", ...agent, paused: !agent.paused },
                agent.paused
                  ? "Agent resumed"
                  : "Agent paused; descendants inherit pause",
              )
            }
          >
            {agent.paused ? <Play size={16} /> : <Pause size={16} />}
          </Button>
        </div>
      </form>
      <div className="agent-status">
        <GitBranch size={15} />
        <span>{running} running tasks</span>
      </div>
    </aside>
  );
}
function NetworkGraph({
  agents,
  counts,
  selected,
  onSelect,
}: {
  agents: Agent[];
  counts: Record<string, Record<string, number>>;
  selected: string;
  onSelect: (s: string) => void;
}) {
  const [rotation, setRotation] = useState(-0.08),
    [tilt, setTilt] = useState(0.24),
    [zoom, setZoom] = useState(1),
    [flat, setFlat] = useState(false);
  const drag = useRef<{
    x: number;
    y: number;
    rotation: number;
    tilt: number;
  } | null>(null);
  const points = agents.map((a) => {
    let x = 0,
      y = -140,
      z = 0;
    const lane = lanes.indexOf(a.lane as (typeof lanes)[number]);
    if (a.id !== "astra") {
      x = (lane - 1.5) * 205;
      y = a.parent === "astra" ? 15 : 165;
      z =
        a.parent === "astra"
          ? lane % 2
            ? 55
            : -55
          : a.id.endsWith("writer")
            ? -85
            : 85;
      if (a.parent !== "astra") x += a.id.endsWith("writer") ? -46 : 46;
    }
    return {
      ...a,
      ...projectedPoint(
        x,
        y,
        flat ? 0 : z,
        flat ? 0 : rotation,
        flat ? 0 : tilt,
        zoom,
      ),
    };
  });
  return (
    <div className="graph-area">
      <div className="graph-toolbar">
        <div className="segmented">
          <button
            className={!flat ? "active" : ""}
            onClick={() => setFlat(false)}
          >
            <Box size={14} /> 3D map
          </button>
          <button
            className={flat ? "active" : ""}
            onClick={() => setFlat(true)}
          >
            <GitBranch size={14} /> Tree
          </button>
        </div>
        <span>Drag to orbit</span>
      </div>
      <svg
        className="network-svg"
        viewBox="0 0 900 520"
        aria-label="Interactive agent delegation tree"
        onPointerDown={(e) => {
          if ((e.target as Element).closest('[role="button"]')) return;
          drag.current = { x: e.clientX, y: e.clientY, rotation, tilt };
          e.currentTarget.setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          if (drag.current && !flat) {
            setRotation(
              Math.max(
                -0.7,
                Math.min(
                  0.7,
                  drag.current.rotation + (e.clientX - drag.current.x) * 0.005,
                ),
              ),
            );
            setTilt(
              Math.max(
                -0.3,
                Math.min(
                  0.65,
                  drag.current.tilt + (e.clientY - drag.current.y) * 0.004,
                ),
              ),
            );
          }
        }}
        onPointerUp={() => (drag.current = null)}
        onPointerCancel={() => (drag.current = null)}
      >
        <defs>
          <pattern
            id="grid"
            width="28"
            height="28"
            patternUnits="userSpaceOnUse"
          >
            <circle cx="1" cy="1" r=".7" fill="#34404d" />
          </pattern>
          <radialGradient id="halo">
            <stop stopColor="#b7ef67" stopOpacity=".08" />
            <stop offset="1" stopColor="#b7ef67" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width="900" height="520" fill="url(#grid)" />
        <ellipse cx="450" cy="170" rx="220" ry="150" fill="url(#halo)" />
        {points
          .filter((p) => p.parent)
          .map((p) => {
            const parent = points.find((a) => a.id === p.parent)!;
            return (
              <g key={p.id}>
                <path
                  d={`M${parent.x},${parent.y + 22} C${parent.x},${(parent.y + p.y) / 2} ${p.x},${(parent.y + p.y) / 2} ${p.x},${p.y - 22}`}
                  stroke={
                    selected === p.id || selected === parent.id
                      ? p.color
                      : "#394551"
                  }
                  strokeWidth={selected === p.id ? 1.6 : 1}
                  fill="none"
                  opacity={p.paused ? 0.35 : 0.8}
                />
                <circle cx={p.x} cy={p.y - 22} r="2" fill={p.color} />
              </g>
            );
          })}
        {[...points]
          .sort((a, b) => b.depth - a.depth)
          .map((p) => {
            const root = p.id === "astra",
              lead = p.parent === "astra",
              active = selected === p.id,
              running = (counts[p.id]?.running || 0) > 0;
            const w = root ? 160 : lead ? 158 : 108,
              h = root ? 74 : lead ? 61 : 44;
            return (
              <g
                className="graph-node"
                key={p.id}
                role="button"
                tabIndex={0}
                aria-pressed={active}
                aria-label={`${p.name}, ${p.role}, ${p.paused ? "paused" : "enabled"}`}
                transform={`translate(${p.x},${p.y})`}
                onClick={() => onSelect(p.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(p.id);
                  }
                }}
                opacity={p.paused ? 0.55 : 1}
              >
                <rect
                  x={-w / 2}
                  y={-h / 2}
                  width={w}
                  height={h}
                  rx={root ? 12 : 8}
                  fill={active ? "#1c2b24" : root ? "#1a2424" : "#131b24"}
                  stroke={active ? p.color : root ? "#607343" : "#3c4a59"}
                  strokeWidth={active ? 1.8 : 1}
                />
                {root && (
                  <text
                    x="0"
                    y="-10"
                    fill={p.color}
                    fontSize="12"
                    textAnchor="middle"
                    letterSpacing="2"
                  >
                    ✳ ORCHESTRATOR
                  </text>
                )}
                <text
                  x="0"
                  y={root ? 12 : lead ? -2 : 5}
                  textAnchor="middle"
                  fill={root ? "#d8f5bc" : "#e0e7ee"}
                  fontSize={root ? 23 : lead ? 15 : 13}
                  fontWeight={root ? 600 : 500}
                >
                  {root
                    ? "Astra"
                    : lead
                      ? p.name
                      : p.id.endsWith("writer")
                        ? "Writer"
                        : "Editor"}
                </text>
                {(root || lead) && (
                  <text
                    x="0"
                    y={root ? 29 : 17}
                    textAnchor="middle"
                    fill="#92a19c"
                    fontSize="11"
                  >
                    {root
                      ? "gpt-6-astra"
                      : p.lane.toUpperCase() + " / 2 WORKERS"}
                  </text>
                )}
                {running && (
                  <circle
                    cx={w / 2 - 10}
                    cy={-h / 2 + 10}
                    r="3"
                    fill="#c6f688"
                    className="pulse"
                  />
                )}
              </g>
            );
          })}
      </svg>
      <div className="graph-controls">
        <button
          aria-label="Zoom out"
          onClick={() => setZoom((z) => Math.max(0.65, z - 0.1))}
        >
          <Minus size={16} />
        </button>
        <span>{Math.round(zoom * 100)}%</span>
        <button
          aria-label="Zoom in"
          onClick={() => setZoom((z) => Math.min(1.25, z + 0.1))}
        >
          <Plus size={16} />
        </button>
        <button
          aria-label="Reset view"
          onClick={() => {
            setRotation(-0.08);
            setTilt(0.24);
            setZoom(1);
          }}
        >
          <Maximize2 size={16} />
        </button>
      </div>
      <div className="graph-id mono">
        NETWORK / 001
        <br />
        <span>4 STUDIOS · 8 WORKERS</span>
      </div>
    </div>
  );
}

function AccountPicker({
  purpose = "publish",
}: {
  purpose?: "publish" | "production";
}) {
  const [search, setSearch] = useState(""),
    [offset, setOffset] = useState(0),
    [selected, setSelected] = useState<{
      id: string;
      handle: string;
      external_id: string;
      platform: string;
    } | null>(null);
  const query = useQuery<{
    items: {
      id: string;
      handle: string;
      external_id: string;
      platform: string;
    }[];
    total: number;
  }>({
    queryKey: ["account-picker", purpose, search, offset],
    queryFn: async () => {
      const r = await fetch(
        `/api/control?picker=accounts&purpose=${purpose}&q=${encodeURIComponent(search)}&offset=${offset}`,
      );
      const v = (await r.json()) as {
        items: {
          id: string;
          handle: string;
          external_id: string;
          platform: string;
        }[];
        total: number;
        error?: string;
      };
      if (!r.ok) throw new Error(v.error || "Accounts unavailable");
      return v;
    },
  });
  const items = query.data?.items || [],
    options =
      selected && !items.some((a) => a.id === selected.id)
        ? [selected, ...items]
        : items;
  return (
    <>
      <Field
        label={
          purpose === "production"
            ? "Find an authorized account"
            : "Find a YouTube account"
        }
      >
        <Input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
          placeholder="Search every registered handle or channel ID"
          maxLength={120}
        />
      </Field>
      <Field
        label={
          purpose === "production" ? "Production account" : "YouTube account"
        }
      >
        <select
          name="account"
          required
          value={selected?.id || ""}
          onChange={(e) =>
            setSelected(options.find((a) => a.id === e.target.value) || null)
          }
        >
          <option value="">
            {query.isPending ? "Loading accounts…" : "Select an account"}
          </option>
          {options.map((a) => (
            <option value={a.id} key={a.id}>
              {a.handle} · {platformInfo[a.platform]?.name || a.platform} ·{" "}
              {a.external_id}
            </option>
          ))}
        </select>
      </Field>
      {query.isError && <p className="form-error">{query.error.message}</p>}
      {(query.data?.total || 0) > 60 && (
        <div className="button-row">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - 60))}
          >
            Previous accounts
          </Button>
          <span className="muted">
            {offset + 1}–{Math.min(offset + 60, query.data!.total)} /{" "}
            {query.data!.total}
          </span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={offset + 60 >= query.data!.total}
            onClick={() => setOffset(offset + 60)}
          >
            More accounts
          </Button>
        </div>
      )}
    </>
  );
}
