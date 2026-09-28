---
type: regex
target: last_message
pattern: '/acs:code EVAL-1\b'
---

The reply prints `handoff.py`'s `continue_with` verbatim: the in-flight step
re-run by name. `/acs:ship EVAL-1` is what it prints only when nothing, or a
parallel group, was in flight.
