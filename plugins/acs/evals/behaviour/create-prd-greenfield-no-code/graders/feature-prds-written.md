---
type: file_exists
path: docs/product/features/online-booking/prd.md
exists: true
---

ADR-0142: the PRD is a hub plus one PRD per feature. The prompt names the four
feature slugs, so each feature's own document sits at
`docs/product/features/<slug>/prd.md`. A run that kept every feature inside
`prd.md` -- the single-file layout this replaced -- writes none of them.
