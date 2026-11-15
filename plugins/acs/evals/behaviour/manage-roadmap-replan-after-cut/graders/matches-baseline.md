---
type: baseline
baseline_file: baseline.jsonl
---

PASS if, like the reference, the run classifies the request as replan, drives /acs:manage-roadmap as a ticketless run through its surveyor (which finds the floor's wont-scheduled drift), author and reviewer subagents, removes the Order tracking milestone and its v2.6.0 Release versions row from docs/product/roadmap.md, keeps Storefront v2.4.0 and Checkout v2.5.0 byte-for-byte, bumps the roadmap from approved v1 to proposed v2 through `acs.py design bump`, leaves the PRD untouched, leaves the roadmap as an uncommitted local change recorded in states.files, and tells the user to review it and run /acs:create-pr, without asking anything the request already answered.
FAIL if order tracking keeps a milestone or a row, another milestone is reworded or re-versioned, the roadmap's version is not bumped or its front matter is hand-edited, the PRD is edited, the run mints a ticket, creates a branch, commits, pushes or opens a PR, claims a PR number or URL, or stops to ask a question.
