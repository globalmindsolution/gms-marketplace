---
type: regex
target: { source: file, path: docs/product/features/order-tracking/prd.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?approved"?\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nversion: 1\n)'
---

ADR-0142: a cut feature moves to Won't have in the hub and keeps its link;
nothing deletes its PRD (retiring it is `/acs:set-doc-status deprecated`, a
person's call). The document is still there, still `approved` at `version: 1`.
A deleted file fails here as a missing target.
