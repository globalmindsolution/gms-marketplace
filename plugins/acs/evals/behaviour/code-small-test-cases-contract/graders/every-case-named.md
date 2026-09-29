---
type: regex
target: { source: file, path: tests/test_list_customers.py }
pattern: '^(?=[\s\S]*\bTC-1\b)(?=[\s\S]*\bTC-2\b)(?=[\s\S]*\bTC-3\b)'
---

On the small path `test-cases.md` is the test contract: one test per `TC-n`
row, each naming its id in the test's docstring (execute.md, step 1). All three
ids must appear in the planned test module. A run that wrote its own tests
from the acceptance criteria, or dropped a case, fails here -- as does a run
that never created the module.
