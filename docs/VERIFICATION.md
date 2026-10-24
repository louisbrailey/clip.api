# Release verification

Development verification performed September 11–15, 2026. This file records the scope of evidence and its limits.

| Requirement | Evidence | Result / limitation |
|---|---|---|
| Portal source and client/server compilation | `npx tsc --noEmit`; `npm run build` | Passed during implementation; final rebuild passed for the source prepared for publication. |
| Durable records and migrations | D1 local execution of all seven generated migrations; actual HTTP workflows | Persisted agents, jobs, usage, audit events, account records and media metadata verified locally. |
| Astra delegation | HTTP creation, claim and completion; structured-output worker fixture tests | Exact `gpt-6-astra` selection verified; no paid model invocation. |
| Worker and agent controls | 149 Python checks plus 48 core HTTP checks | Named worker creation, cross-worker lease denial, individual pause/revoke, per-worker/agent/global concurrency and ancestor pause verified. No mid-call steering. |
| Queue reliability | Atomic-claim SQL tests, competing HTTP callbacks, duplicate completion and stale lease checks | Single winning callback; losing callbacks cannot append children. Budget reservations and daily-ledger checks passed. |
| Original media | Actual leased worker render, private local portal asset registration, download and SHA-256 verification; full FFmpeg decode | Ten-second output and provenance saved locally. Hosted worker and Docker remain inactive/unverified. |
| Media storage/playback | Real MP4 multipart upload plus authenticated byte-range GET | R2 local persistence and HTTP 206 behavior passed. |
| Publishing protections | Concurrent approvals, channel mismatch fixtures, preflight pause, ambiguous response and receipt reconciliation | Duplicate upload queueing blocked; ambiguous uploads not retried automatically. |
| YouTube API path | Fixture tests for OAuth channel check, private metadata, session upload and receipt | No live upload performed. Provider end-to-end validation is credential-gated. |
| X API path | 32 worker/token-store fixtures, 3 official-parser tests and 20 local HTTP approval/recovery checks | No live X request or publication performed. OAuth onboarding, provider access and end-to-end validation remain outstanding. |
| Other platforms | Instagram and Threads use explicit approval, worker fixtures and 28 local HTTP checks. TikTok and Snapchat retain reviewed manual handoff. | Meta adapters are fixture-validated only; live Meta OAuth/provider acceptance remains credential-gated. TikTok/Snapchat direct adapters are not implemented. |
| 10,000 account registry | SQLite test inserted 10,000 authorized-account fixture records and paginated | Storage/query smoke test only, not sustained live platform operations. |
| Million-definition registry | Disposable SQLite fixture with one million lightweight configurations; six indexed page queries | Configuration storage/query evidence only. Million-model execution is not implemented, load-tested or provisioned. Global task cap remains 32. |
| 24/7 runtime | Python loop, Docker/Compose source and persistent receipt journal | Worker unit tests passed. Docker/always-on hosting and valid production worker authentication remain unverified. The existing Sites gateway path was checked separately. |
| Authentication | Anonymous rejection, cross-origin write rejection, worker scope, key revocation | Local authenticated API checks passed. Sites gateway is the production browser identity trust boundary. |

Initial suite: **40 unit/queue tests passed**, plus **42 local HTTP integration checks passed**. Provider tests replace network responses with controlled fixtures. No model or social API calls were made. Browser screenshot/interaction QA was not performed; the UI was compiled and rendered through the local HTTP server. The local in-app preview handoff was queued by the application.

The final delivery report must distinguish a successful private portal publication from the missing credentials, service access, operational readiness and platform adapters above. A production-ready system at the originally requested scale has not been established.

Three additional queue regressions cover a shared expiry-accounting cutoff, paginated access to older assets, and global per-agent status beyond the newest 60 jobs. The publishing account selector now has its own search and pagination. Local migration bootstrap was verified on a fresh database and rerun successfully with no migrations to apply.


## Recurring production release — September 12, 2026

**62 unit/SQL/worker tests**, **42 existing HTTP checks**, and **41 recurrence HTTP checks** pass. Local HTTP checks used an isolated disposable database selected through `CONSTELLATION_LOCAL_STATE`; prior development data was preserved. All provider responses are fixtures; no model or social API requests were made.

Recurrence evidence covers concurrent expansion, lost-response replay, root uniqueness with inherited child metadata, atomic audit rollback, stale edits, historical occurrence collision rejection, account/platform selection, all pause levels, missed-interval coalescing, owner/mode isolation, max-run exhaustion, failure review, scoped discard, future-only brief changes and deterministic rehearsal execution. The existing completion/approval race checks and real local MP4/R2 byte-range checks also passed with the new schema.

The additive migration preserves deployed tables and adds schedules plus nullable job metadata and indexes. Local migration bootstrap and the production build passed. No always-on runtime, paid model capability, OAuth activation, live provider publication, browser interaction QA or million-agent scale was established by these checks.


Machine access was checked against the published portal using its existing Sites token, without rotation. The endpoint returned HTTP 401 with the application's JSON “Worker key is invalid or revoked” response to an intentionally invalid app key. This proves that the supported gateway path reaches the application and retains app-key enforcement; it does not prove successful worker authentication, live jobs or provider access. Worker tests cover portal-only header scope, malformed-token rejection, redacted header errors and HTTPS enforcement. Five loopback HTTP checks confirm that authenticated GET/POST requests do not follow 302/307 redirects or forward credentials to their destination.

## Dynamic network release — September 12, 2026

**73 unit/SQL/worker tests and 135 local HTTP checks passed**: 43 workflow/media checks, 41 recurring-schedule checks, 5 redirect checks and 46 new network checks. The base suite’s competing callback may produce one or two children; this run’s winner produced two and therefore one extra completion check. Four migrations were applied successfully to a new disposable local database; the deployed-core migration regression preserved existing model/instruction settings and backfilled roles, depths and counters.

New evidence covers owner and worker scope, creation replay, transactional counters/audit rollback, capacity rejection, optimistic edits, route/retirement and child/retirement serialized orderings, account→studio→built-in precedence, paused targets, completion nonce fencing, unresolved-work protection, nested restoration, eight-level depth limit, Unicode prefix cursors, child/search pagination, authorized studio-filtered account selection and bounded regular workspace responses. A custom configured writer received and completed an actual locally leased task using a fixture response. No paid model request occurred.

The reproducible local benchmark populated **1,000,000 lightweight agent definitions** in SQLite 3.51.0. Six actual page queries (first, late unique, late repeated-name, narrow final, missing prefix and late child) used the expected indexes. Returned result sets were 0–21 rows, with at most about 1,600 measured SQLite VM steps and 8,946 JSON bytes in these fixtures. The temporary database was approximately 338 MB and was removed after the run. Raw measurements, including environment-specific timings and query plans, are saved in `NETWORK_BENCHMARK.json`.

These measurements are not a live D1 load test, million-job test, concurrency benchmark, deployment SLA or million-model runtime. Existing provider credentials, OAuth, host, real publication and browser interaction QA limitations remain. Source compilation and the production build passed for this release; live provider activation remains separate.

## Narrated original-media release

**147 worker/SQL/process/provider tests, 3 official-parser tests and 257 local HTTP checks passed (407 total).** The narration integration used a fresh disposable portal database, a fresh worker journal, the locally installed `say` voice and an explicit FFmpeg binary. It verified schedule creation and exact replay, script-length rejection, account and editor pauses, stale lease rejection, fresh-worker render/registration/completion, downloaded SHA-256, narration-specific original-rights evidence and full audio decode.

The generated output is `outputs/ambient-recurring-narrated.mp4` with its matching rights record. No provider, model, OAuth, live social publication, Docker host or hosted worker request was made. The deployed portal artifact includes the validated source revision; live worker activation remains credential- and host-gated.


## X video publishing release — September 12, 2026

**105 unit/SQL/worker tests, 3 official-parser tests and 154 local HTTP checks passed (262 total)**. HTTP checks comprise 42 workflow/media, 41 recurrence, 5 credential-redirect, 46 network and 20 X-specific checks. The base completion-race winner created one child in this run. A fresh isolated database applied all five migrations; the new migration only adds immutable job AI-label metadata. Existing deployed migrations remain unchanged.

X fixtures cover exact caption/chunk payloads, account identity and re-verification after token change, authorization, approved AI-label preservation, media processing failure/expiry, final preflight, lease loss, fixed endpoints, provider rejection, lost post responses, receipt preservation after disk-write failure, malformed recovery records and prevention of automatic reposting. Credential tests cover private file permissions, concurrent refresh serialization, replacement token persistence, interrupted-refresh quarantine, new-grant recovery and isolation from completion journals/provider-external requests. The parser tests exercise weighted Latin/CJK/emoji, URLs, joined emoji, normalization and invalid text. Local portal tests exercise actual persisted jobs, concurrent approval, audience-specific consent, caption rejection, pause/preflight, uncertain completion, duplicate-publication locks and manual receipt reconciliation.

TypeScript compilation, the production build and generated migration application passed. No paid model call, real OAuth exchange, X post or YouTube upload occurred. The one-million-definition benchmark belongs to the preceding network release and was not rerun for this additive publication change. Browser interaction QA, Docker execution, always-on hosting, successful production worker authentication, real provider acceptance and sustained operation remain unverified.


## Queued ambient production release — September 12, 2026

**125 unit/SQL/worker/process tests, 3 official-parser tests and 181 local HTTP checks passed (309 total)**. HTTP coverage comprises 42 base workflow/media checks, 41 recurring schedules, 5 credential redirects, 46 network controls, 20 X approvals and 27 ambient-render checks. Six generated migrations applied to isolated disposable local databases. Existing deployed migrations remain unchanged; this release adds only nullable recipe/provenance columns and a unique generated-asset binding.

An actual Python worker rendered a ten-second original pink-noise/ocean-color MP4 with the local FFmpeg 7.1 executable, uploaded it through the leased machine endpoint, completed its task, retrieved the private media and matched its recorded SHA-256. Full video/audio decoding passed. The sample and its portal provenance are saved as `outputs/ambient-queued-ocean.mp4` and `.rights.json`. A separate concurrent-upload fixture selected one canonical asset; a retry returned that same asset, and worker recovery completed without rerendering. No model or social-provider request was made.

Tests cover explicit recipe approval, strict renderer inputs, immutable creation replay and changed-recipe rejection, token-free render claims, browser/machine privilege separation, stale leases, inherited pauses, content digest mismatch, duplicate output races, forbidden success before asset registration and separation from publication approval. Process tests cover credential-free child environments and process-group termination after lease loss. Existing model/provider queue tests also passed. Independent review exercised the actual fenced SQL against disposable SQLite and found no remaining release blocker after the replay fix.

The first render integration attempt stopped on a test-helper argument collision; no renderer/provider request occurred. The helper was corrected and the 27-check suite passed against a fresh local database. Browser interaction QA was not performed. At that release, the Dockerfile included FFmpeg but Docker execution, live host authentication, provider access, recurring render generation, script-to-video production and 24/7 operation remained unverified or unfinished.


## Recurring ambient production release — September 15, 2026

**134 unit/SQL/worker/process tests, 3 official-parser tests and 215 local HTTP checks passed (352 total)**. HTTP coverage comprises 42 base workflow/media, 41 workflow recurrence, 5 credential redirects, 46 network controls, 20 X approvals, 27 queued-render and 34 recurring-render checks. All seven generated migrations applied to a fresh isolated local database. The additive migration adds schedule recipe/approval, output type and creation-intent metadata; the preceding six deployed migrations are unchanged.

Two actual ten-second ambient videos were generated from separate occurrences of one approved schedule. Each was claimed, rendered, registered in private local storage, completed, downloaded, digest-verified and fully decoded with FFmpeg. A fresh worker and empty local journal handled each occurrence; schedule and job context persisted in the portal. An approved schedule edit changed only the next video’s recipe, and the run limit prevented a third occurrence. The test advanced the next occurrence through the operator API; it did not wait an hour or demonstrate continuous 24/7 uptime. Saved outputs are `outputs/ambient-recurring-ocean.mp4`, `outputs/ambient-recurring-forest.mp4`, their rights records, and `outputs/recurring-render-proof.json`.

New coverage includes explicit approval, authorized Ambient account enforcement, live-only render schedules, exact creation replay after expansion, changed-intent rejection, immutable output type, per-occurrence recipe/seed snapshots, competing polls, token-free claims, account/editor/schedule pauses, upload fencing, future-only recipe edits, unresolved-run holds, max-run limits, and absence of implicit model or publishing jobs. Independent read-only review found no release blocker and exercised creation/edit bindings and seven pause gates with disposable SQLite.

The HTTP test found a real D1 interoperability issue: a numeric seed bound into `json_set` became a JSON decimal, rejected by the worker’s strict integer validation. The query now casts that parameter to an integer before serialization; a regression binds a float and checks the parsed JSON type. Both actual recurring videos passed after the fix. An earlier test-helper argument collision was also corrected; its schedule was paused before retry. All records involved were disposable local fixtures.

TypeScript compilation and the production build passed. No model, social API or provider OAuth request was made. Browser interaction QA, successful production worker authentication, Docker execution, an always-on host, real provider acceptance, script-to-video generation and sustained operating throughput remain unverified or unfinished. The historical million-definition SQLite benchmark was not rerun for this additive schedule change.


## Meta publishing release — September 21, 2026

**144 unit/SQL/worker/provider-fixture tests, 3 official-parser tests and 244 local HTTP checks passed (391 total)**, with TypeScript, lint, production build and all eight fresh migrations also passing. Instagram contributed five fixture and 13 HTTP checks; Threads contributed five fixture and 15 HTTP checks. Two actual queued/recurring local videos were fully decoded during these checks. All provider traffic was fixture-local; no Meta credentials, OAuth exchange or live post occurred. Docker is not installed in this environment, so container execution could not be tested on this host.

## Repository maintenance release — October 24, 2026

The repository was checked after new registry advisories appeared. Next, React, Vinext, Vite, the Cloudflare Vite plugin, Wrangler, worker types and their affected transitive packages were upgraded together. Zod was upgraded to the patched v4 package while application schemas continue through its documented `zod/v3` compatibility export. `npm audit --audit-level=low` reported zero vulnerabilities after installation.

The shared developer toolkit recorded successful lint, TypeScript, 149-test Python suite and production-build runs. The build emitted upstream Vinext/Vite sourcemap and ineffective-dynamic-import warnings but completed successfully. No application behavior, database schema, model execution or provider integration changed in this maintenance release. No live model or social-provider call was made.

Weekly Dependabot configuration now proposes npm and GitHub Actions updates. GitHub Actions still runs secret scanning and the full repository checks on every push and pull request. Dependency proposals require review and successful checks; they do not deploy automatically.
