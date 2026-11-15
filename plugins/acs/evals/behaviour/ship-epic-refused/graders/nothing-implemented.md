---
type: regex
target: { source: file, path: src/shop/__init__.py }
pattern: 'checkout|card|charge|payment'
flags: i
match: not_contains
---

"Implementation happens on the children, never on the epic itself." Checkout
code in the product module is the epic implemented as one changeset.
