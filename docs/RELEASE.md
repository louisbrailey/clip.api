# Release and maintenance

This document keeps source, documentation, GitHub and the deployed portal tied to the same reviewed revision. Dependency automation proposes changes; a person or authorized coding agent reviews, tests and merges them.

## Before editing

1. Read `AGENTS.md`, `.toolkit.json`, this document and the README section affected by the change.
2. Run `devkit context .` and verify `git status --short` before modifying files.
3. Keep credentials, `.env.worker`, local D1/R2 state, receipt journals and generated media outside Git.

## Required checks

Run the checks through the shared toolkit so output stays bounded and the complete logs remain in `.toolkit-runs`:

```sh
devkit run -- npm run lint
devkit run -- npm run typecheck
devkit run -- npm run test:worker
devkit run -- npm run build
```

Run focused integration tests when their behavior changed. Use a fresh disposable local database for the HTTP suites, as described in `README.md`. For package changes also run:

```sh
npm audit --audit-level=low
```

Do not describe fixture tests as live provider validation. Record local tests, GitHub CI, deployment, authenticated browser checks, worker-host checks and real-provider checks separately.

## Documentation map

Update documentation in the same commit whenever its claims change:

- `README.md`: product purpose, start path, capabilities, limits and common setup.
- `docs/ARCHITECTURE.md`: trust boundaries, data flow, queue semantics and design constraints.
- `docs/PLATFORMS.md`: provider permissions, account types and publishing availability.
- `docs/OPERATIONS.md`: credentials, worker deployment, recovery and operator procedures.
- `docs/VERIFICATION.md`: dated evidence and explicit unverified boundaries.
- `docs/RELEASE.md`: repository maintenance and release procedure.

## GitHub and dependency updates

GitHub Actions runs repository checks on every push and pull request. Dependabot checks npm and GitHub Actions weekly and opens pull requests. Review changelogs and compatibility, inspect `package-lock.json`, run all gates, and merge only green changes. Dependabot does not update deployed code by itself.

Pinned action SHAs remain pinned. A Dependabot action update must change the SHA and should preserve the readable action/version context in its pull request.

## Publishing

1. Commit the validated source and push it to the private GitHub repository.
2. Confirm the GitHub **Repository checks** workflow succeeds for that commit.
3. Build and package the same commit with the Sites workflow.
4. Save and deploy that exact commit to the existing private Sites project.
5. Confirm the deployment reaches `succeeded` and record its deployment ID and URL in the release evidence or continuity checkpoint.

Do not publish from a dirty tree or claim a successful live integration from deployment status alone.

## Rollback

If a release fails, preserve logs and provider receipts, pause affected workers or accounts, and redeploy the last known-good saved Sites version. Revert the faulty source in a new Git commit; do not rewrite shared history. Resolve `uncertain` publication jobs manually before scheduling replacements.
