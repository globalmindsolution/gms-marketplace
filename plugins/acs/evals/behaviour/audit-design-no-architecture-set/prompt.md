---
description: >-
  /acs:audit-design on a repo with code and a PRD but no architecture set (no
  hld/tech-stack.md anywhere). There is nothing to audit: it should say no
  architecture set was found, point at /acs:create-architecture to baseline
  one, and stop -- writing no document, no code and no gap report, and never
  baselining the design itself or auditing the code against the PRD instead.
expected_outcome: >-
  No file created under docs/, src/ or tests/; no steps/audit-design/iter-*
  gap notes or report.md in the workspace; the reply says no architecture set was found
  and names /acs:create-architecture.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:audit-design skill to check whether our system design docs
still match the code in this repo. Report what it finds. Don't change any
document or any code, don't create tickets, and don't ask me anything.
