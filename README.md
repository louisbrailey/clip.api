# Constellation Studio

A private creative-operations portal for authorized social accounts. Astra delegates production work to studio leads, writers and editors. The operator can inspect the delegation tree, pause agents, edit instructions, set execution limits, schedule work, register accounts, upload source media and inspect the audit trail.

This is a functioning first release with production-oriented queue safeguards. **It is not a verified 24/7 production deployment or a million-model system.** The portal and rehearsals work without external credentials. Live model execution, private YouTube uploads and X video posts require a configured worker, provider credentials and an authenticated machine connection. Instagram, Threads, TikTok and Snapchat currently use manual handoff; their direct publishing adapters are not implemented. No account creation, engagement amplification, scraping, or unauthorized clip reposting is included.

## What runs

- React/Vinext control room with a rotatable 3D projection and a flat tree; 13 built-in agents across Originals, Gaming, Sports and Ambient studios, plus custom agent configurations with paginated branch navigation and name-prefix search.
- GPT-6 Astra (`gpt-6-astra`) as the fixed head orchestrator. Studio models can be changed to models available to your OpenAI API account. No automatic model substitution.
- Durable D1 queue with atomic claims, leases, attempt limits, parent dependencies, cancellation, inherited pauses, per-agent concurrency, global concurrency and token reservations.
- Account-specific recurring production schedules, with pause/resume, run limits, occurrence history, retry-safe creation, missed-interval coalescing and no overlapping unresolved runs.
- Python worker with bounded parallelism, heartbeats, graceful draining, redacted logs and a durable receipt/completion journal.
- Original or licensed MP4 uploads to private R2 storage with provenance records and rights expiry.
- YouTube OAuth refresh, channel-identity verification, resumable-session upload, private visibility, final preflight and provider receipts. Network-ambiguous uploads become `uncertain` and cannot be replayed automatically.
- X user-identity verification, chunked video upload, processing checks and exact approved captions. X publication requires separate audience approval because a post may be public under the account’s settings. Refresh tokens persist privately across restarts; ambiguous post outcomes are held for review. Provider calls are fixture-validated only.
- Queued original ambient-video production with an approved 10–300-second noise/color recipe, private library output and SHA-256 provenance. The worker performs actual FFmpeg rendering without model calls. Local licensed-clip trimming remains available separately.
- Rehearsals explicitly labeled as deterministic fixtures; they call no models and publish nothing.

## Local start

Prerequisites: Node 22.13+ and Python 3.11+ (the worker's tests also ran with the local Python 3.9.6). Use the lockfile.

```sh
npm run install:ci
npm run build
npm run db:migrate:local
npm run dev
```

Open the exact local URL printed by the server. The starter simulates sign-in only on loopback, using the local test identity. Local sign-in is not real OAuth and is not included in deployed production builds.

In the portal, choose **Try a rehearsal**, open **Work queue**, and choose **Run next rehearsal step** four times. Inspect the plan and each dependent task. The configuration tree contains agent definitions; it does not imply that models are running.

## Recurring production

Register an authorized account, open **Schedules**, and choose **New schedule**. Enter that account’s audience, creative direction, original/licensed sources, interval and next start. Use rehearsal mode to inspect delegation without model calls; **Run next rehearsal step** advances due rehearsals. Live schedules expand when the connected worker polls, including while the browser is closed.

The shortest interval is one hour. Blank run limit repeats until paused; a numeric limit counts occurrences created, including failed or discarded runs. Missed intervals coalesce into one catch-up occurrence, maintaining the original elapsed-time cadence. A daily interval can shift local clock time across daylight-saving changes.

Schedule/account/studio/workspace pauses hold future generation and waiting tasks. In-flight calls may finish. Failed or blocked descendants hold the next occurrence for review: retry the task, or use **Discard waiting run** after calls finish. That control cancels waiting tasks for the displayed occurrence and leaves future recurrence enabled. Schedule edits affect future occurrences; existing jobs retain their brief, account and occurrence. **View runs** filters the queue to that schedule. Publication approval remains separate.

## Grow and control the network

Open a studio branch in **Agent network**, select a parent, and choose **Add child agent**. Set its model, production role, instructions and concurrent task limit. The parent, studio and role remain fixed; models and instructions can be edited later. Astra remains the fixed root. Configuration depth is limited to eight levels below Astra.

Choose **Assign production work** to route a studio’s lead/writer/editor role, or override that role for one authorized account. Account overrides take precedence over studio defaults; unassigned roles use the built-in agent. Assignments are resolved when Astra completes its plan. Existing tasks keep their saved agent. A paused assigned agent holds queued work; the system does not silently switch it to a different model.

**Inspect routing assignments** shows the selected agent’s studio/account references and lets you reset them. **View tasks** opens that agent’s work. Retire a custom agent only after clearing its assignments, retiring its active child configurations and resolving its unfinished tasks. Retirement preserves history. Restoration requires enabled ancestors and keeps the restored agent paused. Built-in agents cannot be retired. Edits require the current revision; refresh after a conflicting edit.

The registry allows up to one million configurations, including retired records. The graph loads one focus, its ancestors and up to twelve direct children; search and assignment lists show twenty results per page. This is configuration capacity, not a promise of simultaneous model execution. A disposable SQLite test populated one million lightweight definitions and checked indexed page queries. It did not test a million active models, live D1 service limits or 24/7 throughput. Global execution remains capped at 32 tasks.

## Worker setup

Read [the operating guide](docs/OPERATIONS.md) before enabling live execution. The browser portal is private. For the existing Sites deployment, use its supported machine-access bearer token as `SITES_API_TOKEN`, alongside the separate scoped `CONSTELLATION_WORKER_KEY`. A read-only check of the published portal verified gateway passage and rejection of an invalid application key; authenticated job execution remains to be activated. A custom ingress is an alternative, not required for this Sites connection.

1. Set `CONSTELLATION_URL` to the exact private portal origin and configure its existing `SITES_API_TOKEN`. This token is sent only to that configured portal, including media requests. Do not use a token belonging to another site.
2. In **Controls & setup**, create a worker key. Store it in your secret manager. Only its hash is retained by the portal.
3. Complete the ignored `.env.worker` file, or copy `.env.worker.example` for a new installation, with the URL, Sites token, worker key, OpenAI key, and required OAuth configuration. Never paste provider secrets into the account registry.
4. Start the worker using Docker Compose:

```sh
docker compose up --build -d
docker compose logs --tail=100 worker
```

The Compose definition has restart supervision, a non-root user, a read-only root filesystem and a persistent journal volume. An always-on host still needs to be provisioned. Sleeping a laptop stops reliable 24/7 service. Docker execution has not been validated in the development environment because Docker is unavailable there.

For a local controlled run with environment variables already supplied:

```sh
python3 worker/runtime.py --once
```

OpenClaw is optional. It may supervise this fixed worker process. Do not hand arbitrary shell or browser commands from model output to OpenClaw. No OpenClaw installation or configuration was changed by this project.

## Publishing to X

Register the account’s numeric X user ID and a credential reference, then supply its user OAuth grant to the worker. In **Content library**, approve the exact video and caption for that account’s audience. The portal validates X’s weighted caption limit with the official `twitter-text` parser and offers an explicit AI-label choice. It never silently truncates a caption or adds replies or engagement actions. See [X activation and recovery](docs/OPERATIONS.md#activate-x-video-posts) for scopes, persistent token storage and first-post verification.

## Rendering media

In **Content library**, choose **Create ambient video**. Name the video, choose white/pink/brown noise, a night/ocean/forest color, duration and optional start time, then approve the recipe. A connected worker creates a portrait MP4 and saves it directly in the library. **Open generated video** is available in its task details, and the library exports the rights record and digest. This controlled rendering task uses the built-in Ambient editorial agent’s queue and inherited pauses; it does not invoke Astra or a specialist model. Recurring model workflows still produce text artifacts, and scheduling a render is currently a separate one-time action.

No OpenAI or social OAuth key is needed for rendering alone; the worker still needs the portal’s machine credentials and FFmpeg. Each worker process runs at most one render at a time, within its overall task cap. The Docker definition now installs FFmpeg, but container execution remains unverified here. Lost media-upload responses recover the canonical library asset on a bounded retry. The original recipe is immutable; reopening the form creates a new request. Publishing remains separately approved.

For a standalone local render:

Install FFmpeg, or use the optional pinned helper package:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r worker/render-requirements.txt
.venv/bin/python worker/render.py outputs/original-pink-noise.mp4 --seconds 60 --noise pink
```

This creates an MP4 and a matching `.rights.json` with a SHA-256 digest. For a local source you are licensed to use:

```sh
.venv/bin/python worker/render.py outputs/licensed-edit.mp4 --source /absolute/path/source.mp4 --start 20 --seconds 30 --rights-evidence "License reference and permitted use"
```

Upload the resulting video through **Content library**, recording its rights evidence. This release does not automatically connect LLM scripts to a speech/video-generation service. Each video must be original or licensed and reviewed for the intended use.

## Validation

```sh
npm run typecheck
npm run test:worker
node --experimental-strip-types --test tests/x-text.test.mjs
npm run build
```

After generating `outputs/ambient-pink-noise.mp4` with a 10-second render and starting a fresh local preview database:

```sh
python3 tests/integration.py
python3 tests/integration_schedules.py
python3 tests/integration_machine.py
python3 tests/integration_network.py
python3 tests/integration_x.py
# FFmpeg must be on PATH, or set FFMPEG_BIN to its absolute executable path.
python3 tests/integration_render.py
```

The integration test is hardcoded to loopback. It creates test records, rotates and revokes the local test identity's worker key, and exercises simulated publication receipts. Never adapt it to a production account. Reset only disposable local test state if rerunning. The queued-render release passes 125 worker/SQL/process tests, 3 official-parser tests and 181 local HTTP checks (42 workflow/media, 41 recurrence, 5 redirects, 46 network controls, 20 X checks and 27 render checks); see [verification evidence](docs/VERIFICATION.md). A disposable state directory can be passed to `node scripts/migrate-local.mjs /absolute/disposable/path` and selected when starting development with `CONSTELLATION_LOCAL_STATE=/absolute/disposable/path npm run dev`. Use a new directory for each full integration run.

## Operating boundaries

- 10,000 accounts is a registry limit tested with SQLite records, not proof of OAuth capacity, permission to own that many accounts, or sustained publishing throughput.
- Active execution is capped at 32 tasks per workspace; each workflow has one Astra plan and at most eight sequential delegated tasks. Agent concurrency limits apply to that agent's own jobs. Pauses propagate through the hierarchy.
- A 20,000-token reservation is enforced per live model attempt. The daily ledger separates usage by UTC day. Failed or ambiguous attempts conservatively retain their reservation. This is not a provider-side dollar cap; configure provider spending limits separately.
- The graph begins with 13 built-in agents and supports custom definitions and production assignments. Provisioning millions of active model processes, sharding queues and enterprise tenant administration are not implemented.
- Manual-platform exports consist of source media, rights records and task output packages. There are no fake “connected” platform statuses.
- No platform API call, paid model call, or live social publication was made during validation.

Read [architecture](docs/ARCHITECTURE.md), [platform requirements](docs/PLATFORMS.md), [operations](docs/OPERATIONS.md), and [release verification](docs/VERIFICATION.md).

To reproduce the local registry benchmark, run `python3 tests/benchmark_network.py --rows 1000000 --output /private/tmp/constellation-registry-results.json`. It creates and removes a disposable SQLite fixture (approximately 338 MB for the supplied small definitions), checks index seeking on six page scenarios, and makes no model or platform requests. Timings describe one local run and are not a hosting performance guarantee.
