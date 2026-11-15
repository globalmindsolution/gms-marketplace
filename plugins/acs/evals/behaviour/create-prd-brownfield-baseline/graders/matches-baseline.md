---
type: baseline
baseline_file: baseline.jsonl
---

PASS if, like the reference, the run drives /acs:create-prd as a ticketless run through its subagents to a docs/product/prd.md carrying the eight required sections and the stated facts (the 3.5% conversion metric, the 300 ms latency NFR, the MoSCoW Won't item) and one docs/product/features/<slug>/prd.md per feature, writes no roadmap.md (the milestones are /acs:manage-roadmap's, ADR-0145), gives every document its first version front matter (status proposed, version 1) through `acs.py design init`, leaves the documents as uncommitted local changes recorded in states.files, and tells the user to review them, run /acs:create-pr to commit them and open the PR, and run /acs:manage-roadmap for the milestones, without asking anything the request already answered.
FAIL if the PRD is missing, a roadmap.md is written, invents product facts the request did not give, drops a required section, the run mints a ticket, creates a branch, commits, pushes or opens a PR, claims a PR number or URL, or stops to ask a question.
