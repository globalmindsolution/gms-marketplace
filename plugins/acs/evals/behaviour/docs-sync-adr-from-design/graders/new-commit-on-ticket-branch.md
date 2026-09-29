---
type: regex
target: { source: file, path: .git/logs/refs/heads/task/EVAL-1-store-customers-in-sqlite }
pattern: 'commit: EVAL-1 store customers in SQLite\n[^\n]*\tcommit: EVAL-1 '
---

The ticket branch's own reflog: the entry right after /acs:code's commit is a
new, non-amending commit on THAT branch, in the configured `{ticket_id}
{summary}` format. An ADR left uncommitted, committed elsewhere, or folded
into the code commit fails.
