# Release verification

Development verification performed September 11–12, 2026. This file records the scope of evidence and its limits.

| Requirement | Evidence | Result / limitation |
|---|---|---|
| Portal source and client/server compilation | `npx tsc --noEmit`; `npm run build` | Passed during implementation; final rebuild passed for the source prepared for publication. |
| Durable records and migrations | D1 local execution of all three generated migrations; actual HTTP workflows | Persisted agents, jobs, usage, audit events, account records and media metadata verified locally. |
| Astra delegation | HTTP creation, claim and completion; structured-output worker fixture tests | Exact `gpt-6-astra` selection verified; no paid model invocation. |
| Per-agent controls | HTTP ancestor-pause check; SQL agent/global concurrency tests | Pauses and subsequent-claim configuration verified. No mid-call steering. |
| Queue reliability | Atomic-claim SQL tests, competing HTTP callbacks, duplicate completion and stale lease checks | Single winning callback; losing callbacks cannot append children. Budget reservations and daily-ledger checks passed. |
| Original media | `worker/render.py` produced a ten-second MP4 and SHA-256 rights JSON | Saved locally; container and full FFmpeg decode checked separately. |
| Media storage/playback | Real MP4 multipart upload plus authenticated byte-range GET | R2 local persistence and HTTP 206 behavior passed. |
| Publishing protections | Concurrent approvals, channel mismatch fixtures, preflight pause, ambiguous response and receipt reconciliation | Duplicate upload queueing blocked; ambiguous uploads not retried automatically. |
| YouTube API path | Fixture tests for OAuth channel check, private metadata, session upload and receipt | No live upload performed. Provider end-to-end validation is credential-gated. |
| Other platforms | Explicit registry/manual-handoff UI and official requirements document | Direct adapters not implemented. |
| 10,000 account registry | SQLite test inserted 10,000 authorized-account fixture records and paginated | Storage/query smoke test only, not sustained live platform operations. |
| Million-model scale | Architecture and capacity estimate | Not implemented, load-tested or provisioned. Current global task cap is 32. |
| 24/7 runtime | Python loop, Docker/Compose source and persistent receipt journal | Worker unit tests passed. Docker/always-on hosting and machine ingress remain unverified. |
| Authentication | Anonymous rejection, cross-origin write rejection, worker scope, key revocation | Local authenticated API checks passed. Sites gateway is the production browser identity trust boundary. |

Initial suite: **40 unit/queue tests passed**, plus **42 local HTTP integration checks passed**. Provider tests replace network responses with controlled fixtures. No model or social API calls were made. Browser screenshot/interaction QA was not performed; the UI was compiled and rendered through the local HTTP server. The local in-app preview handoff was queued by the application.

The final delivery report must distinguish a successful private portal publication from the missing credentials, service access, operational readiness and platform adapters above. A production-ready system at the originally requested scale has not been established.

Three additional queue regressions cover a shared expiry-accounting cutoff, paginated access to older assets, and global per-agent status beyond the newest 60 jobs. The publishing account selector now has its own search and pagination. Local migration bootstrap was verified on a fresh database and rerun successfully with no migrations to apply.


## Recurring production release — September 12, 2026

**59 unit/SQL/worker tests**, **42 existing HTTP checks**, and **41 recurrence HTTP checks** pass. Local HTTP checks used an isolated disposable database selected through `CONSTELLATION_LOCAL_STATE`; prior development data was preserved. All provider responses are fixtures; no model or social API requests were made.

Recurrence evidence covers concurrent expansion, lost-response replay, root uniqueness with inherited child metadata, atomic audit rollback, stale edits, historical occurrence collision rejection, account/platform selection, all pause levels, missed-interval coalescing, owner/mode isolation, max-run exhaustion, failure review, scoped discard, future-only brief changes and deterministic rehearsal execution. The existing completion/approval race checks and real local MP4/R2 byte-range checks also passed with the new schema.

The additive migration preserves deployed tables and adds schedules plus nullable job metadata and indexes. Local migration bootstrap and the production build passed. No always-on runtime, paid model capability, OAuth activation, live provider publication, browser interaction QA or million-agent scale was established by these checks.
