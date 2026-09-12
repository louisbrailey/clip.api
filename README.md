# Constellation Studio

A private creative-operations portal for authorized social accounts. Astra delegates production work to studio leads, writers and editors. The operator can inspect the delegation tree, pause agents, edit instructions, set execution limits, schedule work, register accounts, upload source media and inspect the audit trail.

This is a functioning first release with production-oriented queue safeguards. **It is not a verified 24/7 production deployment or a million-model system.** The portal and rehearsals work without external credentials. Live model execution and private YouTube uploads require a configured worker, provider credentials and an authenticated machine connection. Instagram, Threads, X, TikTok and Snapchat currently use manual handoff; their direct publishing adapters are not implemented. No account creation, engagement amplification, scraping, or unauthorized clip reposting is included.

## What runs

- React/Vinext control room with a rotatable 3D projection and a flat tree; 13 configured agents across Originals, Gaming, Sports and Ambient studios.
- GPT-6 Astra (`gpt-6-astra`) as the fixed head orchestrator. Studio models can be changed to models available to your OpenAI API account. No automatic model substitution.
- Durable D1 queue with atomic claims, leases, attempt limits, parent dependencies, cancellation, inherited pauses, per-agent concurrency, global concurrency and token reservations.
- Account-specific recurring production schedules, with pause/resume, run limits, occurrence history, retry-safe creation, missed-interval coalescing and no overlapping unresolved runs.
- Python worker with bounded parallelism, heartbeats, graceful draining, redacted logs and a durable receipt/completion journal.
- Original or licensed MP4 uploads to private R2 storage with provenance records and rights expiry.
- YouTube OAuth refresh, channel-identity verification, resumable-session upload, private visibility, final preflight and provider receipts. Network-ambiguous uploads become `uncertain` and cannot be replayed automatically.
- Original ambient-noise video generator and local licensed-clip trimming via FFmpeg.
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

## Worker setup

Read [the operating guide](docs/OPERATIONS.md) before enabling live execution. The browser portal is private, and its sign-in gateway may reject headless worker traffic even when a Constellation worker key is valid. That connection must be provisioned through a supported machine-access path. The Docker file does not solve gateway access.

1. Configure an authenticated control endpoint with the correct D1/R2 resources.
2. In **Controls & setup**, create a worker key. Store it in your secret manager. Only its hash is retained by the portal.
3. Copy `.env.worker.example` to ignored `.env.worker` and fill the URL, worker key, OpenAI key, and any required OAuth configuration. Never paste provider secrets into the account registry.
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

## Rendering media

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
npm run build
```

After generating `outputs/ambient-pink-noise.mp4` with a 10-second render and starting a fresh local preview database:

```sh
python3 tests/integration.py
python3 tests/integration_schedules.py
```

The integration test is hardcoded to loopback. It creates test records, rotates and revokes the local test identity's worker key, and exercises simulated publication receipts. Never adapt it to a production account. Reset only disposable local test state if rerunning. The recurring release passes 59 worker/queue/recurrence tests, 42 existing HTTP checks and 41 recurrence HTTP checks; see [verification evidence](docs/VERIFICATION.md). A disposable state directory can be passed to `node scripts/migrate-local.mjs /absolute/disposable/path` and selected when starting development with `CONSTELLATION_LOCAL_STATE=/absolute/disposable/path npm run dev`. Use a new directory for each full integration run.

## Operating boundaries

- 10,000 accounts is a registry limit tested with SQLite records, not proof of OAuth capacity, permission to own that many accounts, or sustained publishing throughput.
- Active execution is capped at 32 tasks per workspace; each workflow has one Astra plan and at most eight sequential delegated tasks. Agent concurrency limits apply to that agent's own jobs. Pauses propagate through the hierarchy.
- A 20,000-token reservation is enforced per live model attempt. The daily ledger separates usage by UTC day. Failed or ambiguous attempts conservatively retain their reservation. This is not a provider-side dollar cap; configure provider spending limits separately.
- The current graph contains a fixed 13-agent topology. Dynamically provisioning millions of agents, sharding queues and enterprise tenant administration are not implemented.
- Manual-platform exports consist of source media, rights records and task output packages. There are no fake “connected” platform statuses.
- No platform API call, paid model call, or live social publication was made during validation.

Read [architecture](docs/ARCHITECTURE.md), [platform requirements](docs/PLATFORMS.md), [operations](docs/OPERATIONS.md), and [release verification](docs/VERIFICATION.md).
