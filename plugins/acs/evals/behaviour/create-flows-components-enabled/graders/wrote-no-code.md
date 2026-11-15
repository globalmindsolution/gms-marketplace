---
type: regex
target: files
pattern: '^(?!\.acs/)(?:migrations/|[^\n]*\.(?:py|sql)$)'
flags: m
match: not_contains
---

Documents only: the cancel endpoint, the refund call and the new status are
designed here and built by /acs:code. A `.pyc` cache from importing the
package is not `.py` and does not trip this.
