---
type: regex
target: { source: file, path: .git/logs/refs/heads/task/EVAL-1-serve-the-customer-listing-over-http }
pattern: 'commit: EVAL-1 serve the customer listing over HTTP\n[^\n]*\tcommit: EVAL-1 '
---

The ticket branch's own reflog: the entry right after /acs:code's commit is a
new, non-amending commit on THAT branch, in the configured `{ticket_id}
{summary}` format. Uncommitted, on another branch, or amended fails.
