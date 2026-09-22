# Clip.api / Constellation Studio working instructions

Read: README.md.

GitHub repository name is clip.api; application name remains Constellation Studio. app/components/lib contain the portal, worker the Python worker, tests the fixtures. Preserve rights checks, explicit publication approvals, queue leases, idempotency and budget controls. CI uses fixtures only: no provider credentials, publication, live generation or deployment. Existing Sites deployment is configured separately.

Start with the listed entry points and `devkit context` if available (or read .toolkit.json).
Use rg for scoped text searches and ast-grep for code structure. Read matching sections,
not whole trees. Run focused tests after edits; use full gates for broad changes.
`devkit run -- <command>` keeps complete local logs and prints a bounded tail, preserving
exit status. Read full failures when needed. Do not hide a failed check or claim token
savings without measurement. Keep generated outputs, private state, credentials and
.toolkit-runs out of commits. Shared tools: https://github.com/louisbrailey/developer-toolkit.
