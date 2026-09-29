---
type: regex
target: last_message
pattern: '/acs:review-code EVAL-1\b'
---

The reply prints `handoff.py`'s `continue_with` verbatim: the in-flight
review step re-run by name, not `/acs:code EVAL-1` and not `/acs:ship EVAL-1`.
