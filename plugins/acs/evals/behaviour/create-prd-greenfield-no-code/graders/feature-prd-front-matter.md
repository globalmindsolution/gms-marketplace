---
type: regex
target: { source: file, path: docs/product/features/online-booking/prd.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?proposed"?\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nversion: 1\n)'
---

A feature PRD is a versioned document like the hub (ADR-0122, ADR-0130): the
coordinator gave the new file its first block with `acs.py design init
--status proposed`. A run that left a feature PRD unversioned fails here.
