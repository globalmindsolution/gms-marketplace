---
type: regex
target: files
pattern: '^(?!\.acs/)(?:migrations/|alembic/|[^\n]*\.(?:py|sql)$)'
flags: m
match: not_contains
---

Documents only: no migration file, no DDL script, no ORM model or other
source. The plan and /acs:code write those. A `.pyc` cache from importing the
package is not `.py` and does not trip this.
