---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: 'start = page \* per_page'
---

/acs:review-code is read-only: it judges and writes a verdict, and /acs:code
acts on it. The defective line the scaffold wrote must still be there. A
run that "helpfully" fixed the bug fails here.
