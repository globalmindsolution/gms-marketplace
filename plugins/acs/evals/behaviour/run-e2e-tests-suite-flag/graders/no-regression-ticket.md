---
type: regex
target: files
pattern: '^\.git/acs/state-machine/example-shop/EVAL-\d+/ticket\.json$'
flags: m
match: not_contains
---

`--suite smoke` narrows the run to the smoke suite, which is green, so there
is nothing to triage. A regression ticket means the run also ran `unit` or
`e2e` -- the two red suites it was told to leave alone.
