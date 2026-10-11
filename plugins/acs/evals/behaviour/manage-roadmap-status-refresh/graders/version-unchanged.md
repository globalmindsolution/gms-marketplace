---
type: regex
target: { source: file, path: docs/product/roadmap.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?approved"?\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nversion: 1\n)'
---

A status refresh is not a new version of the roadmap (ADR-0145): the plan did
not change, so the front matter is still `approved` at `version: 1`.
