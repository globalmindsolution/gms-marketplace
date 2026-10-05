---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: 'acs-regression-key: e2e:[^\s"\\]*test_customers_default_page_is_50'
---

The failure path minted a ticket through `new-ticket.py` (the counter's first
id is EVAL-1), and its description carries the dedup marker with the suite's
exact key `e2e` and the failing test's id parsed from the unittest output. The
`e2e:__suite__` fallback is for output with no parseable test id; this output
names one, so the fallback here is a triage miss.
