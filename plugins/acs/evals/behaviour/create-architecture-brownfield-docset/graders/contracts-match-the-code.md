---
type: regex
target: { source: file, path: docs/architecture/lld/contracts.md }
pattern: '^(?=[\s\S]*/health)(?=[\s\S]*/customers)(?=[\s\S]*\boffset\b)(?=[\s\S]*\blimit\b)'
---

Grounded in the codebase: the contracts name both real endpoints and the
listing's `offset`/`limit` parameters (src/shop/__init__.py, README.md). A
doc set written from the PRD alone describes checkout and never these.
