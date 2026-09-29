---
type: regex
target: { source: file, path: .git/logs/refs/heads/task/EVAL-1-raise-the-customer-page-size-to-50 }
pattern: 'commit: EVAL-1 raise the customer page size to 50\n[^\n]*\tcommit: EVAL-1 '
---

The ticket branch's own reflog: the entry right after /acs:code's commit is a
new, non-amending commit on THAT branch, subject in the configured
`{ticket_id} {summary}` format. A README edited but not committed, committed on
a new branch, or folded into the code commit (`commit (amend):`) fails.
