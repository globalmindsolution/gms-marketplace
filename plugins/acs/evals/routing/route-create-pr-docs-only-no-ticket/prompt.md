---
description: >-
  Docs-only mode: documents with no ticket and no code run go up through this
  skill too. Borrows the vocabulary of /acs:create-prd and
  /acs:create-architecture on purpose -- the PRD and the ADRs are named --
  while the documents are already written and the request is only to ship
  them. Never names the skill.
expected_outcome: Routes to acs:create-pr.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The PRD amendment and the two new ADRs are written and sitting uncommitted under docs/. There's no ticket for them; commit them and put them up as a pull request so the team can review the documents.
