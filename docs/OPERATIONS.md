# Operating guide and activation gates

## Current state

The software can run the private portal, persist configuration and queued jobs, demonstrate delegation in rehearsal mode, and render original ambient media locally. It does not currently operate real accounts or paid models. No always-on host, OpenAI API key, platform OAuth grant or machine gateway connection was provisioned during development.

Do not turn “registered” into “connected” in user-facing reporting: account registration is a record, and live authorization is separately verified by the worker. The dashboard's worker status is based on an actual recent heartbeat. The maximum registry size was tested as stored SQLite records; actual 10,000-account publishing has not been established.

## Activate a worker

1. Provision a durable host capable of running the Docker Compose worker. Store its journal volume on persistent storage. Docker and host provisioning remain unverified here.
2. Establish machine access to the control API. A private Sites URL normally uses a browser sign-in gateway. A Constellation key authenticates inside the application and does not bypass that gateway. Use a platform-supported service connection or a separately provisioned machine-only ingress with equivalent access to the intended D1/R2 data. This is an unresolved deployment prerequisite, not a completed integration.
3. Keep browser ingress behind a gateway that authenticates and overwrites identity headers. Never expose the unwrapped application publicly. `deploy/machine-entry.mjs` is an optional deny-by-default wrapper for machine-only ingress; only its API routes are admitted, and all browser identity headers/cookies are removed. Resource binding and host approval are still needed.
4. Configure OpenAI account access for `gpt-6-astra` and the selected specialist models. Use a secret manager or the OpenAI Developers credential workflow. The OpenAI Developers plugin/key workflow was unavailable in the task environment, so no key was created or copied from unrelated projects. Set provider-side spend limits as well as the portal's token allowance.
5. Rotate a worker key in the portal and load the displayed key into `CONSTELLATION_WORKER_KEY`. Set `CONSTELLATION_URL`, `OPENAI_API_KEY`, and `WORKER_CONCURRENCY`. Optional `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` are supported only if that access layer was separately configured; they are not a Sites sign-in workaround.
6. Start with `WORKER_CONCURRENCY=1` and a 20,000-token portal allowance. Run a single live workflow, inspect the actual response and usage, then increase limits only after verifying provider access and costs.
7. Confirm a recent heartbeat, successful lease renewal, valid Astra manifest, sequential child execution and a persisted result after a process restart.

## Activate YouTube uploads

Create or use an approved Google developer app and complete user OAuth consent for the intended channel with `youtube.upload` and `youtube.readonly`. This project does not include a public OAuth onboarding UI. Supply the resulting refresh token only through the worker secret configuration.

A registered account's credential reference, such as `YOUTUBE_AMBIENT`, names a worker environment variable containing JSON with `client_id`, `client_secret` and `refresh_token`. The worker exchanges it for an access token and checks the channel returned by `channels.list(mine=true)` before touching media. It never accepts a user-supplied bearer token from the UI.

Upload original or licensed MP4 media, record provenance and expiry, register the matching account, and approve an exact private upload. The worker rechecks lease validity, account pause, workspace pause and rights immediately before dispatch. Verify the first private upload and metadata in YouTube Studio. Only then consider a separately reviewed public-publishing extension; this release always uses private visibility.

## Pauses, failures and receipts

- **Pause studio:** stops new dispatch. A request already accepted by a provider can finish.
- **Pause an agent:** that agent and descendants cannot claim new work. Its instruction/concurrency edits apply to subsequent claims. This does not steer a model request already running.
- **Pause account:** prevents new recurring production, account-linked task claims and upload claims; blocks final publishing preflight when noticed before dispatch.
- **Pause schedule:** holds generation and all queued descendants for that schedule, including after a running Astra call completes. Existing calls drain.
- **Discard waiting run:** cancels waiting/failed tasks for that occurrence only. It refuses while any task in the occurrence is running or uncertain. Future recurrence remains enabled, and the run still counts toward its limit.
- **Cancel:** available for tasks that have not started. Running requests drain; the UI does not falsely claim remote cancellation.
- **Failed model task:** inspect the error and retry only after fixing its cause. Maximum three attempts.
- **Expired model lease:** bounded requeue after a delay. Worst-case reservation remains charged because spend may be unknown.
- **Uncertain upload:** inspect YouTube Studio and the persistent worker journal. Enter the verified video ID/URL through the reconciliation form. Never create another upload merely because the HTTP response was lost.
- **Pending completion:** the journal contains the exact completion payload and receipt. The worker tries to report it on restart. A stale lease cannot overwrite a new owner; the operator must reconcile any accepted upload manually.

A token allowance is a conservative dispatch guard, not exact billing or a dollar cap. Every model attempt reserves 20,000 tokens. Successful attempts use reported token usage; failed/unknown attempts retain the reservation. Reservations carry across UTC midnight until resolved, and the per-attempt ledger retains the charged day.

## Recurring workflow operation

The worker’s authenticated claim request expands up to ten eligible schedules before attempting a task claim. No open browser tab is required for live recurrence. Without a connected polling worker, live schedules remain due; no hosted background cron is implied. Rehearsal schedules expand only when an operator advances a rehearsal.

Each root snapshots schedule ID, nominal occurrence timestamp, account, studio, mode and brief. Descendants retain those fields, and their model input includes only the platform/handle/account ID, not credential references or tokens. Schedule edits apply to later roots and require the current revision. An edit cannot reuse an occurrence timestamp already assigned to a root. Refresh an open edit form if its revision became stale during generation or another control change.

Due generation checks authorization and account, studio, Astra, workspace and schedule pauses. Any queued, running, failed, blocked or uncertain task belonging to a schedule prevents its next occurrence. Review unresolved work and retry or discard it; a successful plan root alone does not mean its workflow is finished. The daily token budget and concurrency limits still apply to every subsequent claim.

Creation uses a client-generated request ID retained across retries: the first saved request for that ID wins. Creating a different schedule requires a fresh ID. Controls and their audit records commit together. Generation inserts a unique root and advances its schedule in one transaction; the counter advances only if that exact root exists at the current occurrence. Missed intervals produce one catch-up run, not a backlog of every missed slot. The registry is capped at 10,000 schedules, independent of execution capacity.

## Supervision and recovery

The included Compose service uses `restart: unless-stopped`, a non-root user, dropped capabilities, read-only root filesystem, persistent journal storage, bounded memory and log rotation. Restart policy is not an uptime guarantee. Configure independent host availability alerts and monitor worker heartbeats, queue age, error rate, oldest uncertain uploads and provider quotas before relying on 24/7 operation.

Back up D1 and R2 using the hosting provider's supported backup/export facilities and retain the worker journal volume. Perform a restore drill into an isolated environment before production use. Backup scheduling, restore testing, sustained load testing and alert delivery are not implemented or verified in this release.

## Validation and limits

- TypeScript compilation and production asset build are required before publishing source changes.
- Run `npm run test:worker` for worker safety, actual queue SQL and registry tests.
- The local integration script requires a disposable local database and generated sample MP4. It rotates the development identity's worker key and creates fixture records. Do not run it on production.
- Hosted smoke verification must use the authenticated owner's access. A successful deployment status proves artifact publication, not live model execution or social API approval.
- Current direct publishing covers private YouTube uploads only. Other adapters, OAuth onboarding, dynamic agent provisioning, retention automation, hard monetary limits, multi-host scale and operational SLA verification remain future work.
