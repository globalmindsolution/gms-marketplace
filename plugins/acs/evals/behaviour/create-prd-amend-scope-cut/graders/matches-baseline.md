---
type: baseline
baseline_file: baseline.jsonl
---

PASS if, like the reference, the run finds the existing PRD, runs /acs:create-prd in amend mode as a ticketless run through its surveyor, author and reviewer subagents, moves order tracking from Should to Won't and adds it to Out of scope in docs/product/prd.md, leaves every other section byte-for-byte unchanged, bumps its version front matter from approved v1 to proposed v2 through `acs.py design bump`, leaves docs/product/roadmap.md and every feature PRD untouched at approved v1 (the roadmap is /acs:manage-roadmap's, ADR-0145), leaves the PRD as an uncommitted local change recorded in states.files, and tells the user to review it, run /acs:create-pr to commit it and open the PR, and run /acs:manage-roadmap to re-plan the roadmap, without asking anything the request already answered.
FAIL if the PRD is regenerated or reworded outside the confirmed sections, order tracking stays a Should-have, the roadmap is edited or re-versioned, the PRD's version is not bumped or its front matter is edited by hand, the run mints a ticket, creates a branch, commits, pushes or opens a PR, claims a PR number or URL, or stops to ask a question.
