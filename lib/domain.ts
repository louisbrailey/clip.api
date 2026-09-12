import { z } from "zod";
export const lanes = ["originals", "gaming", "sports", "ambient"] as const;
export const platforms = [
  "youtube",
  "instagram",
  "threads",
  "x",
  "tiktok",
  "snapchat",
] as const;
export const platformInfo: Record<
  string,
  { name: string; support: string; note: string; url: string }
> = {
  youtube: {
    name: "YouTube",
    support: "Worker adapter",
    note: "OAuth and quota approval required. Uploads default to private; unverified projects are restricted to private uploads.",
    url: "https://developers.google.com/youtube/v3/docs/videos/insert",
  },
  instagram: {
    name: "Instagram",
    support: "Manual handoff",
    note: "Professional account and approved Meta permissions required. Direct publishing adapter is not included in this release.",
    url: "https://developers.facebook.com/docs/instagram-platform/content-publishing",
  },
  threads: {
    name: "Threads",
    support: "Manual handoff",
    note: "Threads OAuth and publishing permissions required. Direct publishing adapter is not included in this release.",
    url: "https://developers.facebook.com/docs/threads/posts",
  },
  x: {
    name: "X",
    support: "Worker adapter",
    note: "Reviewed video posts use the account’s existing audience and may be public. User OAuth, media.write permission and API access are required. Live provider validation is pending.",
    url: "https://help.x.com/en/rules-and-policies/authenticity",
  },
  tiktok: {
    name: "TikTok",
    support: "Manual handoff",
    note: "TikTok rejects internal team-account utilities for Direct Post. Export a package for creator review and manual posting.",
    url: "https://developers.tiktok.com/docs/en/content-sharing-guidelines",
  },
  snapchat: {
    name: "Snapchat",
    support: "Manual handoff",
    note: "Public Profile API access is allowlist-only. Export a package until an approved integration is implemented.",
    url: "https://developers.snap.com/marketing-api/Public-Profile-API/GetStarted",
  },
};
export type Agent = {
  id: string;
  parent: string | null;
  name: string;
  role: string;
  lane: string;
  model: string;
  paused: number;
  concurrency: number;
  instructions: string;
  color: string;
  task_role: string;
  core: number;
  archived: number;
  depth: number;
  revision: number;
  child_count: number;
};
const tracks = [
  ["originals", "Original studio", "Original scripts & concepts", "#b7ef67"],
  ["gaming", "Gaming desk", "Your footage & licensed clips", "#7ea5ff"],
  ["sports", "Sports desk", "Licensed edits & commentary", "#ffb977"],
  ["ambient", "Ambient studio", "Original sound & meditation", "#9edbcb"],
];
const seedAgents = [
  {
    id: "astra",
    parent: null,
    name: "Astra",
    role: "Head orchestrator",
    lane: "all",
    model: "gpt-6-astra",
    paused: 0,
    concurrency: 1,
    instructions:
      "Delegate original or licensed creative work to the relevant studio. Keep tasks specific, bounded, and reviewable. Never create engagement, account creation, or unauthorized scraping tasks.",
    color: "#c6f688",
  },
  ...tracks.flatMap(([lane, name, role, color]) => [
    {
      id: lane,
      parent: "astra",
      name,
      role,
      lane,
      model: "gpt-5.6-sol",
      paused: 0,
      concurrency: 2,
      instructions: `Coordinate ${role.toLowerCase()}. Work only from authorized source material.`,
      color,
    },
    {
      id: `${lane}-writer`,
      parent: lane,
      name: "Creative writer",
      role: "Scripts & production briefs",
      lane,
      model: "gpt-5.6-sol",
      paused: 0,
      concurrency: 2,
      instructions:
        "Create a distinctive, useful script and clear production directions. Do not invent rights or claims about source material.",
      color,
    },
    {
      id: `${lane}-editor`,
      parent: lane,
      name: "Editorial review",
      role: "Quality & publishing package",
      lane,
      model: "gpt-5.6-sol",
      paused: 0,
      concurrency: 1,
      instructions:
        "Review the supplied draft, identify unresolved issues, and prepare accurate titles, descriptions and an edit list. Do not certify legal rights.",
      color,
    },
  ]),
];
export const initialAgents: Agent[] = seedAgents.map((a) => ({
  ...a,
  task_role:
    a.id === "astra"
      ? "orchestrator"
      : a.parent === "astra"
        ? "lead"
        : a.id.endsWith("writer")
          ? "writer"
          : "editor",
  core: 1,
  archived: 0,
  depth: a.id === "astra" ? 0 : a.parent === "astra" ? 1 : 2,
  revision: 1,
  child_count: a.id === "astra" ? 4 : a.parent === "astra" ? 2 : 0,
}));
export type NetworkAgent = Agent & {
  running: number;
  queued: number;
  route_count: number;
};
export type NetworkBranch = {
  focus: NetworkAgent;
  ancestors: Agent[];
  children: NetworkAgent[];
  next: string | null;
  total: number;
};
export type Job = {
  id: string;
  parent: string | null;
  depends: string | null;
  agent: string;
  title: string;
  brief: string;
  kind: string;
  mode: string;
  status: string;
  lane: string;
  result: string;
  error: string;
  created: number;
  scheduled: number;
  attempts: number;
  tokens: number;
  reserve: number;
  lease: string | null;
  lease_until: number | null;
  account: string | null;
  asset: string | null;
  receipt: string;
  approved: number;
  made_with_ai: number;
  schedule_id: string | null;
  occurrence: number | null;
};
export type Account = {
  id: string;
  platform: string;
  handle: string;
  lane: string;
  external_id: string;
  credential_ref: string;
  authorized: number;
  paused: number;
  daily_limit: number;
  created: number;
};
export type Schedule = {
  id: string;
  account: string;
  title: string;
  brief: string;
  mode: "live" | "rehearsal";
  interval_minutes: number;
  next_run: number;
  paused: number;
  generated_count: number;
  max_runs: number | null;
  revision: number;
  created: number;
  updated: number;
  handle: string;
  platform: string;
  lane: string;
  account_paused: number;
  pending: number;
  running: number;
  review: number;
  pending_occurrence: number | null;
};
export type Asset = {
  id: string;
  name: string;
  rights: string;
  evidence: string;
  expires: number | null;
  size: number;
  created: number;
  object_key: string;
  mime: string;
};
export type Event = {
  id: string;
  message: string;
  type: string;
  job: string | null;
  created: number;
};
export type Settings = {
  paused: number;
  concurrency: number;
  daily_tokens: number;
  worker_seen: number | null;
  has_worker_key: boolean;
};
export type State = {
  agent_counts: Record<string, Record<string, number>>;
  lane_counts: Record<string, Record<string, number>>;
  agents: Agent[];
  agent_total: number;
  jobs: Job[];
  accounts: Account[];
  assets: Asset[];
  schedules: Schedule[];
  schedule_total: number;
  events: Event[];
  settings: Settings;
  counts: Record<string, number>;
  tokens_today: number;
  reserved_today: number;
  job_total: number;
  account_total: number;
  asset_total: number;
  now: number;
};
export const workflowInput = z.object({
  title: z.string().trim().min(3).max(160),
  brief: z.string().trim().min(15).max(6000),
  lane: z.enum(lanes),
  mode: z.enum(["rehearsal", "live"]),
  scheduled: z.number().int().nonnegative().optional(),
});
export const scheduleInput = z
  .object({
    request_id: z.string().uuid().optional(),
    id: z.string().uuid().optional(),
    revision: z.number().int().positive().optional(),
    account: z.string().uuid(),
    title: z.string().trim().min(3).max(160),
    brief: z.string().trim().min(15).max(6000),
    mode: z.enum(["rehearsal", "live"]),
    interval_minutes: z.number().int().min(60).max(525600),
    next_run: z.number().int().nonnegative().max(4102444800000),
    max_runs: z.number().int().min(1).max(1000000).nullable(),
    paused: z.boolean(),
  })
  .refine(
    (v) => (v.id ? v.revision !== undefined : v.request_id !== undefined),
    {
      message:
        "Supply a revision for edits or a stable request ID for creation",
    },
  );
export const accountInput = z.object({
  platform: z.enum(platforms),
  handle: z.string().trim().min(2).max(100),
  lane: z.enum(lanes),
  external_id: z.string().trim().min(1).max(120),
  credential_ref: z.string().regex(/^[A-Z][A-Z0-9_]{2,79}$/),
  authorized: z.literal(true),
  daily_limit: z.number().int().min(1).max(100).default(1),
});
export const agentInput = z.object({
  revision: z.number().int().positive(),
  id: z.string(),
  paused: z.boolean(),
  concurrency: z.number().int().min(1).max(16),
  model: z.string().regex(/^[a-zA-Z0-9][a-zA-Z0-9.:/_-]{1,100}$/),
  instructions: z.string().trim().min(1).max(6000),
});
export const planInput = z
  .array(
    z.object({
      title: z.string().min(3).max(160),
      brief: z.string().min(10).max(6000),
      role: z.enum(["lead", "writer", "editor"]),
    }),
  )
  .min(1)
  .max(8);
export function rightsValid(
  asset: Pick<Asset, "rights" | "evidence" | "expires">,
  now: number,
) {
  return (
    ["original", "licensed", "public-domain"].includes(asset.rights) &&
    asset.evidence.trim().length >= 10 &&
    (!asset.expires || asset.expires > now)
  );
}
export function projectedPoint(
  x: number,
  y: number,
  z: number,
  rotation: number,
  tilt: number,
  zoom: number,
) {
  const rx = x * Math.cos(rotation) + z * Math.sin(rotation),
    rz = -x * Math.sin(rotation) + z * Math.cos(rotation);
  const ry = y * Math.cos(tilt) - rz * Math.sin(tilt),
    depth = y * Math.sin(tilt) + rz * Math.cos(tilt),
    scale = (900 / (900 + depth)) * zoom;
  return { x: 450 + rx * scale, y: 260 + ry * scale, scale, depth };
}
