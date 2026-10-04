---
type: regex
target: files
pattern: '^(?=[\s\S]*^docs/architecture/hld/cross-cutting\.md$)(?=[\s\S]*^docs/architecture/hld/integration-map\.md$)'
flags: m
---

The existing set predates two documents the Output contract now requires:
`hld/cross-cutting.md` is always written, and `integration-map` is a default
`design.hld_types` entry. A re-run keeps the set where it is and writes every
file of the contract, so both are created in place beside the regenerated
views -- not in a new location.
