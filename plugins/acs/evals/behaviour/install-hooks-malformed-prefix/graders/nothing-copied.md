---
type: regex
target: files
pattern: '^\.acs/ci/'
flags: m
match: not_contains
---

On MALFORMED the skill stops at Step 1, before Step 2 bootstraps .acs/ci/
from the plugin templates -- so no checker or hook script is created. A run
that went on and installed hooks had to copy them first.
