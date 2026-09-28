---
type: file_exists
path: src/shop/search.py
exists: false
---

The plan's task 1 creates `src/shop/search.py`. The pre-hook refuses the run
before any implementer exists, so the module must not appear. On its own this
passes a run that did nothing; the reply grader catches that.
