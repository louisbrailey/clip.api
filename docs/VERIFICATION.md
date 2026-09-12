# Release verification

Development verification performed September 11–12, 2026. This file records the scope of evidence and its limits.

| Requirement | Evidence | Result / limitation |
|---|---|---|
| Portal source and client/server compilation | `npx tsc --noEmit`; `npm run build` | Passed during implementation; final rebuild passed for the source prepared for publication. |
| Durable records and migrations | D1 local execution of all five generated migrations; actual HTTP workflows | Persisted agents, jobs, usage, audit events, account records and media metadata verified locally. |
| Astra delegation | HTTP creation, claim and completion; structured-output worker fixture tests | Exact `gpt-6-astra` selection verified; no paid model invocation. |
| Per-agent controls | HTTP ancestor-pause check; SQL agent/global concurrency tests | Pauses and subsequent-claim configuration verified. No mid-call steering. |
| Queue reliability | Atomic-claim SQL tests, competing HTTP callbacks, duplicate completion and stale lease checks | Single winning callback; losing callbacks cannot append children. Budget reservations and daily-ledger checks passed. |
| Original media | `worker/render.py` produced a ten-second MP4 and SHA-256 rights JSON | Saved locally; container and full FFmpeg decode checked separately. |
| Media storage/playback | Real MP4 multipart upload plus authenticated byte-range GET | R2 local persistence and HTTP 206 behavior passed. |
| Publishing protections | Concurrent approvals, channel mismatch fixtures, preflight pause, ambiguous response and receipt reconciliation | Duplicate upload queueing blocked; ambiguous uploads not retried automatically. |
| YouTube API path | Fixture tests for OAuth channel check, private metadata, session upload and receipt | No live upload performed. Provider end-to-end validation is credential-gated. |
| X API path | 32 worker/token-store fixtures, 3 official-parser tests and 20 local HTTP approval/recovery checks | No live X request or publication performed. OAuth onboarding, provider access and end-to-end validation remain outstanding. |
| Other platforms | Explicit registry/manual-handoff UI and official requirements document | Instagram, Threads, TikTok and Snapchat direct adapters not implemented. |
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


## X video publishing release — September 12, 2026

**105 unit/SQL/worker tests, 3 official-parser tests and 154 local HTTP checks passed (262 total)**. HTTP checks comprise 42 workflow/media, 41 recurrence, 5 credential-redirect, 46 network and 20 X-specific checks. The base completion-race winner created one child in this run. A fresh isolated database applied all five migrations; the new migration only adds immutable job AI-label metadata. Existing deployed migrations remain unchanged.

X fixtures cover exact caption/chunk payloads, account identity and re-verification after token change, authorization, approved AI-label preservation, media processing failure/expiry, final preflight, lease loss, fixed endpoints, provider rejection, lost post responses, receipt preservation after disk-write failure, malformed recovery records and prevention of automatic reposting. Credential tests cover private file permissions, concurrent refresh serialization, replacement token persistence, interrupted-refresh quarantine, new-grant recovery and isolation from completion journals/provider-external requests. The parser tests exercise weighted Latin/CJK/emoji, URLs, joined emoji, normalization and invalid text. Local portal tests exercise actual persisted jobs, concurrent approval, audience-specific consent, caption rejection, pause/preflight, uncertain completion, duplicate-publication locks and manual receipt reconciliation.

TypeScript compilation, the production build and generated migration application passed. No paid model call, real OAuth exchange, X post or YouTube upload occurred. The one-million-definition benchmark belongs to the preceding network release and was not rerun for this additive publication change. Browser interaction QA, Docker execution, always-on hosting, successful production worker authentication, real provider acceptance and sustained operation remain unverified.
