---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcheckout: moving from main to task/EVAL-1-cap-the-customer-page-size-at-100\n$'
---

The package commit is built through a temporary index and never moves HEAD.
HEAD's reflog still ends at the scaffold's checkout, so the run committed
nothing on the ticket branch.
