---
type: regex
target: files
pattern: '^tests/e2e/test_[^/]*\.py$'
flags: m
---

A new suite file exists where the repo keeps its e2e suites, collected by the
configured command's `-p 'test_*.py'`. `files` lists only paths the run
CREATED, so the seeded `test_health_e2e.py` never satisfies this.
