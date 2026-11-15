---
type: regex
target: files
pattern: '^(?:docs/|(?:src|tests)/.*\.py$)'
flags: m
match: not_contains
---

The audit is read-only, and with no architecture set it has nothing to read:
it must not baseline one itself (that is /acs:create-architecture's job, on
its own delivery ticket) or touch the code. A `.pyc` cache is not `.py` and
does not trip this.
