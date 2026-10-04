---
type: regex
target: files
pattern: '^docs/architecture/lld/orders/components/'
flags: m
match: not_contains
---

`component-detail` and `class` are opt-in and this repo keeps the default
design.lld_types, so neither is enabled: nothing is written under
components/.
