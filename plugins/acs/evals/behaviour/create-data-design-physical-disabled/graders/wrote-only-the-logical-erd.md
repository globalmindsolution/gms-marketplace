---
type: regex
target: files
pattern: '^docs/(?!architecture/lld/README\.md$|architecture/lld/orders/README\.md$|architecture/lld/orders/data/logical-erd\.md$)'
flags: m
match: not_contains
---

With the physical schema disabled the only data document is the logical ERD
(plus the feature README the first LLD skill creates). Any other new file
under docs/ -- the disabled type under another name, a flow, an HLD edit as
a new file -- fails.
