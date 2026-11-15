---
type: regex
target: { source: file, path: docs/architecture/lld/contracts.md }
pattern: '^# Contracts\n\n## Contracts\n\n- `GET /health` returns `ok`\.\n- `GET /customers\?offset=&limit=` returns `\{items, offset, limit\}`; limit\n  defaults to 20\.\n- `exports` Redis queue: one CSV line per customer, pushed nightly by\n  export-worker \(see nightly-export\)\.\n(?![\s\S])'
---

The low-level design is not this skill's: `lld/` belongs to the Design
skills, written per ticket (ADR-0118), and a re-run "never touches `lld/`".
The scaffold's contracts file -- stale Redis queue contract and all -- must
survive byte for byte. The pattern is the whole file, anchored at both ends,
so any edit, truncation or deletion fails it.
