---
type: file_exists
path: docs/product/features/*/prd.md
exists: true
---

ADR-0142: the PRD is a hub plus one PRD per feature. The prompt does not name
the slugs, so any `docs/product/features/<slug>/prd.md` proves the run wrote
the layout; a run that kept every feature inside `prd.md` writes none.
