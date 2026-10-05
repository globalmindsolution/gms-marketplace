---
type: regex
target: { source: file, path: docs/product/roadmap.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?proposed"?\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nversion: 1\n)'
---

No `roadmap.md` existed, so the coordinator gave the new document its first
version front matter with `acs.py design init --status proposed`
(ADR-0122, ADR-0130): it opens with `status: proposed` at `version: 1`,
ready for `/acs:set-doc-status` once the team approves it. A run that
never versioned it fails here.
