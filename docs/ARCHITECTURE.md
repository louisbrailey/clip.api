# Architecture and execution contract

The portal is a control plane, not an execution claim. Agent records describe configuration. Job records describe actual work. The distinction is visible in the UI: configured agent count, actual queued/running tasks, recent worker heartbeat and explicit live/rehearsal modes.

```mermaid
flowchart TD
  Owner[Authenticated owner] --> Portal[Private control room]
  Portal --> Queue[(D1 jobs, agents, usage and audit)]
  Portal --> Media[(Private R2 media)]
  Worker[Bounded Python worker pool] -->|scoped machine key| Queue
  Worker --> Astra[GPT-6 Astra plan]
  Astra --> Manifest[Validated manifest: 1–8 tasks]
  Manifest --> Queue
  Worker --> Specialists[Configured studio models]
  Worker --> Review[Approved immutable upload task]
  Review --> YouTube[Private YouTube upload]
  YouTube --> Receipt[Durable provider receipt]
  Receipt --> Queue
```

Astra's model is explicitly `gpt-6-astra`, a documented Responses API model with structured outputs. API account access is not inferred from availability in the Codex app. [OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-6-astra).

## Job lifecycle

A new workflow creates a `plan` job assigned to Astra. A completed manifest creates sequential `draft` children with a parent ID, prior dependency and one of three allowed roles. The server chooses each role's agent within the workflow's studio. A model cannot add arbitrary tools, alter permissions, enqueue a publication or create accounts. User-supplied agent instructions are bounded input, and every model call receives fixed production boundaries.

`queued → running → succeeded | failed | uncertain`. A claimed job has a server timestamp, a unique lease token and a 180-second lease. The worker renews every 40 seconds. Completion is fenced by owner, job ID, running state, lease token and expiry; it uses an atomic batch with a unique completion marker. Losing competing callbacks cannot insert children or accounting rows. Identical completed callbacks are idempotent.

Model lease expiry requeues with a 30-second delay, to a maximum of three attempts. Unknown spend is retained in the usage ledger. Explicit model failures require operator retry. Dependency-blocked jobs recover after their dependency succeeds. Expired publishing leases enter `uncertain`; they are never automatically reuploaded. The local worker journal preserves dispatch intent, accepted provider receipts and pending completion payloads.

Claims enforce owner scope, due time, dependencies, attempt cap, inherited pauses, per-agent concurrency, workspace concurrency, reservations and publishing eligibility in the same SQL update. A stable claim request ID prevents an ambiguous HTTP retry from claiming a second task. Each SQL statement is separately prepared; transactionally related statements run in a D1 batch.

## Media and publication

R2 stores immutable per-upload objects under owner-scoped random keys. D1 stores name, size, rights basis, evidence and expiry. The API requires MP4 container bytes and a size under 50 MB. Container recognition is not full codec or malware validation; FFmpeg decoding is part of the local rendering workflow. Browser and worker downloads are authenticated, including byte-range playback.

A publication approval names an exact source object, account, title, description and schedule. These fields have no editing endpoint after creation. A partial unique index prevents a second queued, running, uncertain or successful publication for the same asset in the workspace. Rights and pauses are rechecked at claim and immediately before the provider request. The YouTube worker validates the OAuth channel ID and always uploads privately. The operator verifies publication receipts in the platform.

## Authentication and secrets

Browser identity comes from dispatch-owned Sites sign-in. The production boundary must strip and replace all `oai-authenticated-user-*` headers. Never expose the unwrapped Vinext application on an untrusted standalone network: those headers are trusted only behind the authenticated Sites gateway. Local sign-in middleware strips spoofed headers and applies a development identity only to loopback requests.

Worker keys contain 256 random bits; only SHA-256 hashes are stored. They are owner-scoped and limited to claiming, heartbeats, completion, preflight and media retrieval. Keys cannot mutate operator settings, register accounts or read the browser control room. Rotation and revocation are audited. Provider credentials remain in the worker's environment. The optional `deploy/machine-entry.mjs` wrapper rejects browser routes and strips browser identity headers for separately provisioned machine ingress. It does not provision that ingress or grant access to Sites-managed storage.

Browser writes require the same origin. Database statements are parameterized. Models have no shell, browser, engagement tools or arbitrary HTTP access. Provider requests use fixed HTTPS endpoints and reject redirects. Upload-session URLs must remain on the expected Google API host. Logs expose error categories rather than secrets or provider response bodies.

## Capacity and remaining work

The current bounded implementation uses one D1 database, 13 configured agents and up to 32 simultaneous tasks. Each page returns at most 60 jobs/accounts and 100 audit events; summary counts query the complete workspace. One D1 database is single-threaded and has a 10 GB storage limit. Million-job throughput requires measured performance, ownership-based sharding, archival and a different queue/execution strategy. [Cloudflare D1 limits](https://developers.cloudflare.com/d1/platform/limits/).

A capacity illustration—not a result: one million jobs/day averages 11.57 jobs/second. At 30 seconds per job, approximately 347 concurrent workers would be occupied before redundancy or burst headroom. At 1,500 tokens/job, demand would be 1.5 billion tokens/day. Neither these limits nor that spend is authorized or provisioned by a portal setting.


## Recurring account workflows

`schedules` stores account-specific briefs, elapsed-time cadence, the next nominal occurrence, mode, pause state, run limit/count and an optimistic edit revision. `jobs.schedule_id` and `jobs.occurrence` link every root and descendant. A partial unique index on owner/schedule/occurrence applies only to roots, allowing children to share immutable occurrence context.

Every live worker claim expands at most ten due schedules. Candidate selection filters pauses, account authorization, mode, limits and all unresolved jobs before its limit. The same eligibility query is used inside `INSERT … SELECT` to revalidate concurrent controls. A D1 transaction inserts a root, advances only the occurrence tied to that new root ID, and records one event. Advancement jumps over missed intervals while preserving cadence. A replay or competing expander cannot create or count the same root twice.

Generation snapshots the account’s studio and brief; completion propagates account/schedule/occurrence fields. Claims independently enforce schedule and account pause, plus the chosen studio pause even when the task is assigned to Astra. Changing schedule mode or brief does not rewrite existing work. Failed/blocked/uncertain descendants prevent overlap until resolved or safely discarded. These schedules produce production artifacts, never publication approval.

Operator saves use stable creation request IDs, optimistic revisions on edits, atomic audit records and rejection of previously used occurrence timestamps. The portal paginates schedules and can filter all jobs by schedule ID. This is bounded single-workspace orchestration; it does not implement million-agent provisioning, queue sharding or a 24/7 hosted worker by itself.


The supported Sites machine path uses two credentials: the site's existing machine-access token in `OAI-Sites-Authorization`, plus the application's scoped worker key in `Authorization`. Only the `Portal` HTTP client attaches the Sites token; model and social provider requests do not receive it. HTTPS and bearer-format validation reject malformed values before header construction, HTTP configuration errors are redacted, and authenticated requests refuse all redirects. No new Sites token was generated or rotated during development.
