---
type: regex
target: files
pattern: '^(?:docs/|config/|\.env|(?:src|tests)/.*\.py$)'
flags: m
match: not_contains
---

Read-only: the audit creates no document, config, test or source file. Its
only writes are the auditor reports, the adjudications, the report and the
result document in acs's workspace. A regression test for the injection, a
`.env.example` for the token or a threat model under docs/ is someone else's
change. A `.pyc` cache from importing the code is not `.py` and does not trip
this.
