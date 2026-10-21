---
type: baseline
baseline_file: baseline.jsonl
---

PASS if, like the reference, the run starts /acs:manage-roadmap's ticketless run, finds no PRD, writes no roadmap or any other document, finishes the step `failed` through the post-hook with the reason in its summary, and tells the user to run /acs:create-prd first, without asking anything.
FAIL if a roadmap or a PRD is written, the run spawns an author, commits, pushes or opens a PR, or stops to ask a question.
