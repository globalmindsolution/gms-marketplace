---
type: regex
target: files
pattern: '^(?:tests/|src/|\.acs/state-machine/example-shop/EVAL-\d+/)'
flags: m
match: not_contains
---

No suite written, no product code, and no regression ticket minted: there was
no failure to triage.
