---
type: regex
target: { source: file, path: .git/logs/refs/heads/task/EVAL-1-rename-shop-page-size-to-shop-customers-page-size }
pattern: 'commit: EVAL-1 rename SHOP_PAGE_SIZE to SHOP_CUSTOMERS_PAGE_SIZE\n[^\n]*\tcommit: EVAL-1 '
---

The ticket branch's own reflog: the entry right after /acs:code's commit is a
new, non-amending commit on THAT branch, in the configured `{ticket_id}
{summary}` format. Edited but uncommitted, committed elsewhere, or folded
into the code commit (`commit (amend):`) fails.
