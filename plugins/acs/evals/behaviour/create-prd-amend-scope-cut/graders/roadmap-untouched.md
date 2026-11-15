---
type: regex
target: { source: file, path: docs/product/roadmap.md }
pattern: '^-{3}(?=(?:(?!\n-{3}\n)[\s\S])*\nstatus: "?approved"?\n)(?=(?:(?!\n-{3}\n)[\s\S])*\nversion: 1\n)(?=[\s\S]*### Order tracking — v2\.6\.0)(?=[\s\S]*\|\s*v2\.6\.0\s*\|\s*Order tracking\s*\|)'
---

ADR-0145: the roadmap is `/acs:manage-roadmap`'s, not create-prd's. The
amendment cuts a feature the roadmap still schedules, and that is for the
roadmap skill to re-plan: `roadmap.md` keeps its Order tracking milestone and
v2.6.0 row, still `approved` at `version: 1`. A run that edited or re-versioned
it fails here.
