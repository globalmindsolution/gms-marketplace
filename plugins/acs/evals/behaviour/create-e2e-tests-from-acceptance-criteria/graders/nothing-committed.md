---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: HTTP front with /health and its e2e harness\n$'
---

HEAD's reflog still ends at the scaffold's last entry (`commit: HTTP front
with /health and its e2e harness`): the run made no commit, and created,
switched, reset or stashed nothing -- each of those appends to it. Only
/acs:create-pr branches and commits (ADR-0127); the suites stay uncommitted in
the working tree, named in the result's files.
