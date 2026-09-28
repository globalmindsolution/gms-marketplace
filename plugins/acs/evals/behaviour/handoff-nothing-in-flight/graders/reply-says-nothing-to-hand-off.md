---
type: regex
target: last_message
pattern: 'nothing (?:was |is )?(?:in flight|to hand off)|no step (?:was |is )?(?:in flight|in progress)'
flags: i
---

Step 5: when `handoff.py` reports `"step": null`, say explicitly that nothing
was in flight -- there is nothing to hand off.
