---
type: regex
target: last_message
pattern: 'mismatch|(?:checked out|current branch|HEAD|on) `?main`?[^\n]*(?:ticket|recorded|expected)[^\n]*branch|task/EVAL-1-raise-the-customer-page-size-to-50[^\n]*(?:not|isn''t|instead)|not (?:on )?the ticket branch'
flags: i
---

The error is surfaced: the checkout is on main, not the recorded ticket
branch.
