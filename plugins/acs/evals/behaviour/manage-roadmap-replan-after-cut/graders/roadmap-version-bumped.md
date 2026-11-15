---
type: regex
target: { source: file, path: docs/product/roadmap.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?proposed"?\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nversion: 2\n)'
---

The plan changed, so the coordinator bumped the block the scaffold gave the
roadmap (`approved` v1) with `acs.py design bump` (ADR-0130): `status:
proposed` at `version: 2`, re-opened for the team to approve again.
