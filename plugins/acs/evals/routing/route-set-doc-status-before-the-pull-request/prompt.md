---
description: >-
  Borrows the vocabulary of /acs:create-pr on purpose -- the pull
  request, reviewers -- while the request still belongs to this skill:
  the PR comes later, and what is asked now is to record the approval on
  the documents. It tests that the description, not a keyword, decides
  the route. Never names the skill.
expected_outcome: Routes to acs:set-doc-status.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't open the pull request yet. Before anyone does, the reviewers want the search feature's design documents themselves to say they're approved -- record that on them first; the PR comes later.
