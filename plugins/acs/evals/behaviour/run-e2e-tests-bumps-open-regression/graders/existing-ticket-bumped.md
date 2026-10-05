---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"description"\s*:\s*"acs-regression-key: e2e:__suite__\\n(?:[^"\\]|\\.)*First seen on the standing run of 2026-09-27\.(?:[^"\\]|\\.)*run-\d{4}-?\d{2}-?\d{2}T'
---

The comment-bump appends to EVAL-1's `description` (load, append, save): the
marker line and the original text are still there, and after them comes this
run's fresh evidence, which names the new `run-<ISO8601>` run id. A run that
skipped the ticket, or replaced its description, fails here.
