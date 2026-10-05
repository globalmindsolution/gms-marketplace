---
type: regex
target: { source: file, path: src/shop/store.py }
pattern: 'WHERE email = ''%s''" % email'
---

/acs:review-code is read-only: it judges and writes a verdict, and /acs:code
acts on it. The vulnerable line the scaffold wrote must still be there; a
run that "helpfully" parameterised the query fails here.
