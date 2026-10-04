---
description: >-
  Docs-only mode (--docs): documents with no ticket and no code run go up
  through this skill too. The documents are already written, so the request is
  only to commit and ship them, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-pr.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

The PRD amendment and the two new ADRs are written and sitting uncommitted under docs/. There's no ticket for them; commit them and put them up as a pull request so the team can review the documents.
