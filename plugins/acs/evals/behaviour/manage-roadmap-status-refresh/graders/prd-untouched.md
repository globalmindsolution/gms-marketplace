---
type: regex
target: { source: file, path: docs/product/prd.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?approved"?\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nversion: 1\n)'
---

ADR-0145: the roadmap skill schedules the PRD's features; it never edits the
PRD. `prd.md` is still `approved` at `version: 1`, as the scaffold left it.
