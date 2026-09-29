---
type: regex
target: { source: file, path: .git/logs/refs/heads/task/EVAL-1-serve-the-customer-listing-over-http }
pattern: 'commit: EVAL-1 test cases\n[^\n]*\tcommit: EVAL-1 '
---

The ticket branch's own reflog: the entry right after the scaffold's last
commit is a new, non-amending commit on THAT branch, in the configured
`{ticket_id} {summary}` format. A suite left uncommitted, committed on another
branch, or folded into an amended commit (`commit (amend):`) fails.
