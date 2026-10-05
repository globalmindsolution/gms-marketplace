---
type: regex
target: { source: file, path: docs/product/roadmap.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?proposed"?\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nversion: 2\n)'
---

The amendment changed `roadmap.md`, so the coordinator bumped the block the
scaffold gave it (`approved` v1) with `acs.py design bump` (ADR-0130):
it now reads `status: proposed` at `version: 2` -- a changed document
shows a bumped version, re-opened for the team to approve again. An
amendment that left the version at 1, or stripped the block, fails here.
