---
type: baseline
baseline_file: baseline.jsonl
---

PASS if, like the reference, the run classifies the request as status, runs `acs.py roadmap status --write` and no subagent, so docs/product/roadmap.md shows Checkout `delivered` (its Status line and its Release versions cell) and Storefront and Order tracking still `planned`, leaves the front matter at approved v1, leaves the roadmap as an uncommitted local change recorded in states.files through the post-hook, and reports the milestones, without asking anything.
FAIL if a status is written by hand or disagrees with the tickets, the version is bumped, a surveyor, author or reviewer is spawned, the PRD is edited, the run commits, pushes or opens a PR, or stops to ask a question.
