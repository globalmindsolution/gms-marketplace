---
type: regex
target: files
pattern: '^tests/e2e/test_[^/\n]*\.py$'
flags: m
---

A new suite file where the repo keeps its e2e suites, collected by the
configured command's `-p 'test_*.py'`. The seeded `test_health_e2e.py` was not
created by the run, so it never satisfies this.
