---
type: regex
target: files
pattern: '^(?:docs/|(?:src|tests)/.*\.py$)'
flags: m
match: not_contains
---

Read-only: the audit creates no document and no code. Its only writes are the
gap notes, the joined report and the result document in acs's workspace,
outside the repo's own tree. A run that "fixed" the design by adding an
orders view or an lld/orders/ contract wrote someone else's documents. A
`.pyc` cache from importing the package to check it is not `.py` and does
not trip this.
