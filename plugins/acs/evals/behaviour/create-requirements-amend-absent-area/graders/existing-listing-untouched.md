---
type: regex
target: { source: file, path: docs/requirements/functional/customer-listing.md }
pattern: '^# Customer listing\n\n## Behaviour\n\n- `GET /customers` MUST return `\{items, offset, limit\}` \{#listing-shape\}\n- The listing MUST default `limit` to 20 per page \{#listing-page-size\}\n- The listing MUST start at `offset` 0 when none is given \{#listing-offset\}\n(?![\s\S])'
---

Augment-only-absent: an existing area file is preserved byte-for-byte, never
overwritten -- not re-marked DRAFT, not re-worded, not cross-linked. The
pattern is the whole file, anchored at both ends.
