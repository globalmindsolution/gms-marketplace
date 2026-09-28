---
type: regex
target: files
pattern: '^docs/requirements/(?:functional|non-functional)/(?!order-listing\.(?:evidence\.)?md$)'
flags: m
match: not_contains
---

The confirmed augmentation is exactly one area: the only area files this run
creates are order-listing.md and its evidence sidecar.
