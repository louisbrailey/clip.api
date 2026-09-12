# Operating guide and activation gates

## Current state

The software can run the private portal, persist configuration and queued jobs, demonstrate delegation in rehearsal mode, and render original ambient media locally. It does not currently operate real accounts or paid models. No always-on host, OpenAI API key or platform OAuth grant was provisioned during development. The existing Sites machine-access token was located without generating or rotating credentials; a read-only production request verified gateway passage and scoped application-key rejection.

Do not turn “registered” into “connected” in user-facing reporting: account registration is a record, and live authorization is separately verified by the worker. The dashboard's worker status is based on an actual recent heartbeat. The maximum registry size was tested as stored SQLite records; actual 10,000-account publishing has not been established.

## Activate a worker

1. Provision a durable host capable of running the Docker Compose worker. Store its journal volume on persistent storage. Docker and host provisioning remain unverified here.
2. For this Sites deployment, load the existing machine-access bearer token into `SITES_API_TOKEN` and use the exact portal origin as `CONSTELLATION_URL`. The worker sends `OAI-Sites-Authorization` only on portal API/media requests. The separate `CONSTELLATION_WORKER_KEY` still authenticates and scopes every application action. The read-only gateway probe used an invalid app key and received the application’s JSON rejection; it did not claim jobs or establish successful live execution. Generating a new Sites token requires an explicit token request and invalidates the existing token immediately; do not rotate it casually.
3. Keep browser ingress behind a gateway that authenticates and overwrites identity headers. The existing Sites connection above preserves that boundary. If you instead choose separate ingress, `deploy/machine-entry.mjs` is an optional deny-by-default wrapper: only machine API routes are admitted, all browser identity headers/cookies are removed, and equivalent D1/R2 binding and host approval remain necessary.
4. Configure OpenAI account access for `gpt-6-astra` and the selected specialist models. Use a secret manager or the OpenAI Developers credential workflow. The OpenAI Developers plugin/key workflow was unavailable in the task environment, so no key was created or copied from unrelated projects. Set provider-side spend limits as well as the portal's token allowance.
5. Rotate a worker key in the portal and load the displayed key into `CONSTELLATION_WORKER_KEY`. Set `CONSTELLATION_URL`, `OPENAI_API_KEY`, and `WORKER_CONCURRENCY`. Optional `CF_ACCESS_CLIENT_ID` and `CF_ACCESS_CLIENT_SECRET` are supported only if that access layer was separately configured; they are not a Sites sign-in workaround.
6. Start with `WORKER_CONCURRENCY=1` and a 20,000-token portal allowance. Run a single live workflow, inspect the actual response and usage, then increase limits only after verifying provider access and costs.
7. Confirm a recent heartbeat, successful lease renewal, valid Astra manifest, sequential child execution and a persisted result after a process restart.

## Activate YouTube uploads

Create or use an approved Google developer app and complete user OAuth consent for the intended channel with `youtube.upload` and `youtube.readonly`. This project does not include a public OAuth onboarding UI. Supply the resulting refresh token only through the worker secret configuration.

A registered account's credential reference, such as `YOUTUBE_AMBIENT`, names a worker environment variable containing JSON with `client_id`, `client_secret` and `refresh_token`. The worker exchanges it for an access token and checks the channel returned by `channels.list(mine=true)` before touching media. It never accepts a user-supplied bearer token from the UI.

Upload original or licensed MP4 media, record provenance and expiry, register the matching account, and approve an exact private upload. The worker rechecks lease validity, account pause, workspace pause and rights immediately before dispatch. Verify the first private upload and metadata in YouTube Studio. Only then consider a separately reviewed public-publishing extension; this release always uses private visibility.

## Activate X video posts

Use an X developer application and obtain a user OAuth 2.0 authorization-code grant with PKCE (`S256`), state verification, an exact registered redirect URI and scopes `tweet.read tweet.write users.read media.write offline.access`. OAuth onboarding is not built into this portal. The grant must authorize the intended account and the developer project must have the required API access and credits. [Official authorization flow](https://docs.x.com/fundamentals/authentication/oauth-2-0/authorization-code).

Register the numeric X user ID, not a handle, in the account’s external ID field. A credential reference such as `X_AMBIENT` names a worker environment variable containing JSON with `client_id` and `refresh_token`; confidential applications also supply `client_secret`. Keep these values in worker secrets. The worker checks `/2/users/me` before uploading, and repeats the identity check if it obtains a different access token before post creation.

The worker stores refreshed credentials under the persistent journal volume’s private `credentials/` directory. Files are mode 0600, the directory is 0700, and per-reference file locks serialize refreshes. The replacement refresh token is written durably before provider work continues. Use a local persistent filesystem supporting atomic rename, directory synchronization and process file locks; shared multi-host credential storage is not supported. Token files are secrets and must be protected in backups as well as the live volume.

An interrupted or ambiguous refresh leaves the credential quarantined. Obtain a fresh user authorization grant and update the initial refresh token in the secret configuration to reset that state. Changing only the client secret retains the current stored refresh token. Do not delete or manually reset token state to retry an old refresh grant: the provider may already have invalidated it.

Upload an original or licensed MP4, select the X account, review the exact caption and explicitly approve that account’s audience. This creates a real post according to the account’s settings and may be public. The queue title is internal, and the caption is validated using X’s official weighted-text parser. Select **Label this post as made with AI** when appropriate; the choice is saved with the immutable publication task. [Create-post fields](https://docs.x.com/x-api/posts/create-post), [character counting](https://docs.x.com/fundamentals/counting-characters).

The worker initializes media, sends 4 MiB chunks as base64 JSON, finalizes, checks processing and expiry, then repeats portal preflight before creating the post. Validate the first live upload’s actual API responses, video playback, caption, account audience, AI label and receipt before enabling sustained work. Tests use provider fixtures, so platform-side acceptance, quota and live media processing remain unverified. [Initialize](https://docs.x.com/x-api/media/initialize-media-upload), [append](https://docs.x.com/x-api/media/append-media-upload), [finalize](https://docs.x.com/x-api/media/finalize-media-upload), [status](https://docs.x.com/x-api/media/get-media-upload-status), [media encoding](https://docs.x.com/x-api/media/upload-media).

Post creation has no assumed idempotency contract. A lost response, unclear provider result or expired publishing lease becomes uncertain and cannot automatically publish again. A known post ID is retained even if an intermediate journal write fails; the worker then attempts to persist and report its completion. A crash with only a provider receipt checkpoint may require manual reconciliation because it lacks the completion lease envelope. Inspect the real account and record the verified receipt in the portal. A definite rejected preparation/post task requires fixing its cause and a fresh approval; it is not automatically retried. X API charges and quotas are separate from the portal’s model-token allowance.

## Operate queued ambient rendering

The **Create ambient video** form queues a fixed original-media recipe under the built-in Ambient editorial agent. Supported recipes are white, pink or brown noise, three plain background colors, a server-generated seed and 10–300 seconds. Every video has a 720×1280 portrait frame and gently faded synthesized audio. No source path, remote URL, shell text, arbitrary filter or model-generated command is accepted. The one-time task may have a future start; recurring schedules and automatic script-to-speech/video generation are separate capabilities and do not yet invoke this renderer.

Install FFmpeg on the worker, or set the operator-controlled `FFMPEG_BIN` path. The Dockerfile includes the distribution’s FFmpeg package; Docker startup remains to be validated on the chosen host. The render subprocess receives only a minimal executable environment, without model/social/portal secrets. One render runs per worker process, with a single encoder thread, a bounded duration-dependent timeout and a 16 MiB output cap. Rendering consumes worker CPU and storage but reserves zero model tokens. Other workers remain subject to workspace and per-agent task limits.

The worker checks its live lease and portal controls before rendering and before uploading. A lost heartbeat stops the process group. Workspace or inherited agent pauses hold new claims and reject subsequent render preflight/media registration; they may allow the already-running local encode to finish. Shutdown uses the existing graceful drain; forced termination discards temporary files and a later leased attempt may rerender.

Generated media uses a separate machine endpoint scoped to the job and current lease. The server computes the digest, derives original-media provenance from the saved recipe and selects a unique asset for that job. Each upload attempt has its own private object key, so a stale or duplicate attempt cannot overwrite the winner. Asset insertion, job binding and audit are transactional; completion additionally requires that binding. A lost transfer response can safely recover the saved asset on retry. An uncertain database response may leave an unreferenced private object; automated orphan cleanup/retention remains outstanding. Never delete a potentially committed object merely because a request timed out.

Inspect the video’s playback, audio, duration and rights record in the library, then approve a separate publication. **Retry task** is available for failed renders within the three-attempt limit; a retry with a canonical saved asset skips encoding/upload. The local end-to-end test produced and fully decoded `outputs/ambient-queued-ocean.mp4`; it did not activate the hosted worker.

The procedural audio uses FFmpeg’s noise source with fixed recipe parameters. [FFmpeg noise-source documentation](https://ffmpeg.org/ffmpeg-filters.html#anoisesrc).

## Pauses, failures and receipts

- **Pause studio:** stops new dispatch. A request already accepted by a provider can finish.
- **Pause an agent:** that agent and descendants cannot claim new work. Its instruction/concurrency edits apply to subsequent claims. This does not steer a model request already running.
- **Pause account:** prevents new recurring production, account-linked task claims and upload claims; blocks final publishing preflight when noticed before dispatch.
- **Pause schedule:** holds generation and all queued descendants for that schedule, including after a running Astra call completes. Existing calls drain.
- **Discard waiting run:** cancels waiting/failed tasks for that occurrence only. It refuses while any task in the occurrence is running or uncertain. Future recurrence remains enabled, and the run still counts toward its limit.
- **Cancel:** available for tasks that have not started. Running requests drain; the UI does not falsely claim remote cancellation.
- **Failed model task:** inspect the error and retry only after fixing its cause. Maximum three attempts.
- **Expired model lease:** bounded requeue after a delay. Worst-case reservation remains charged because spend may be unknown.
- **Uncertain publication:** inspect the relevant YouTube or X account and the persistent worker journal. Enter the verified provider ID/URL through the reconciliation form. Never create another publication merely because the HTTP response was lost.
- **Pending completion:** the journal contains the exact completion payload and receipt. The worker tries to report it on restart. A stale lease cannot overwrite a new owner; the operator must reconcile any accepted upload manually.

A token allowance is a conservative dispatch guard, not exact billing or a dollar cap. Every model attempt reserves 20,000 tokens. Successful attempts use reported token usage; failed/unknown attempts retain the reservation. Reservations carry across UTC midnight until resolved, and the per-attempt ledger retains the charged day.

## Recurring workflow operation

The worker’s authenticated claim request expands up to ten eligible schedules before attempting a task claim. No open browser tab is required for live recurrence. Without a connected polling worker, live schedules remain due; no hosted background cron is implied. Rehearsal schedules expand only when an operator advances a rehearsal.

Each root snapshots schedule ID, nominal occurrence timestamp, account, studio, mode and brief. Descendants retain those fields, and their model input includes only the platform/handle/account ID, not credential references or tokens. Schedule edits apply to later roots and require the current revision. An edit cannot reuse an occurrence timestamp already assigned to a root. Refresh an open edit form if its revision became stale during generation or another control change.

Due generation checks authorization and account, studio, Astra, workspace and schedule pauses. Any queued, running, failed, blocked or uncertain task belonging to a schedule prevents its next occurrence. Review unresolved work and retry or discard it; a successful plan root alone does not mean its workflow is finished. The daily token budget and concurrency limits still apply to every subsequent claim.

Creation uses a client-generated request ID retained across retries: the first saved request for that ID wins. Creating a different schedule requires a fresh ID. Controls and their audit records commit together. Generation inserts a unique root and advances its schedule in one transaction; the counter advances only if that exact root exists at the current occurrence. Missed intervals produce one catch-up run, not a backlog of every missed slot. The registry is capped at 10,000 schedules, independent of execution capacity.

## Agent assignment and retirement

Use the network’s branch controls to create a specialist under the relevant studio, then assign the required production role at studio or account level. Account assignments override the studio’s default. A configuration can exist without receiving work. Creating a million definitions does not provision a million API clients or increase any worker, token or provider limit.

Assignment changes apply to children created by later completed Astra plans. Existing tasks retain their target, including tasks already queued. Pausing a routed agent holds its tasks and descendants. Inspect the actual queue and worker heartbeat to distinguish configured, enabled, queued and running states.

Before retiring a custom agent, open **Inspect routing assignments** and reset its references, resolve unfinished tasks, and retire nonretired child configurations. Completed history remains available. A restored configuration stays paused; restore and enable its ancestors first. Built-in fallback agents are permanent. A conflict message means another change won the revision race; refresh the selected configuration or assignment before retrying.

## Supervision and recovery

The included Compose service uses `restart: unless-stopped`, a non-root user, dropped capabilities, read-only root filesystem, persistent journal storage, bounded memory and log rotation. Restart policy is not an uptime guarantee. Configure independent host availability alerts and monitor worker heartbeats, queue age, error rate, oldest uncertain uploads and provider quotas before relying on 24/7 operation.

Back up D1 and R2 using the hosting provider's supported backup/export facilities and retain the worker journal volume. Perform a restore drill into an isolated environment before production use. Backup scheduling, restore testing, sustained load testing and alert delivery are not implemented or verified in this release.

## Validation and limits

- TypeScript compilation and production asset build are required before publishing source changes.
- Run `npm run test:worker` for worker safety, actual queue SQL and registry tests.
- The local integration script requires a disposable local database and generated sample MP4. It rotates the development identity's worker key and creates fixture records. Do not run it on production.
- Hosted smoke verification must use the authenticated owner's access. A successful deployment status proves artifact publication, not live model execution or social API approval.
- Current direct publishing covers private YouTube uploads and explicitly approved X video posts; both provider paths are fixture-validated only. Other adapters, OAuth onboarding, automatic model infrastructure provisioning, retention automation, hard monetary limits, multi-host scale and operational SLA verification remain future work.
