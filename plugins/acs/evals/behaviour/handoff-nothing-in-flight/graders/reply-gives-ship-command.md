---
type: regex
target: last_message
pattern: '/acs:ship EVAL-1\b'
---

The reply still prints `continue_with` verbatim, which with nothing in flight
is `/acs:ship EVAL-1` -- the workflow resumes from the run's own cursor. A
guessed `/acs:docs-sync EVAL-1` or `/acs:code EVAL-1` fails here.
