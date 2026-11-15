---
type: regex
target: { source: file, path: docs/product/features/saved-carts/prd.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?approved"?\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nversion: 1\n)'
---

ADR-0142: a feature the amendment does not touch keeps its document -- and its
version. `saved-carts` is still `approved` at `version: 1`; a run that bumped or
rewrote it as a side effect of editing the hub fails here.
