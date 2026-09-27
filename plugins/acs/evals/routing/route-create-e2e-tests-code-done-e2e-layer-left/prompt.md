---
description: >-
  Borrows the vocabulary of /acs:code on purpose -- it opens on the code
  being done -- while the request still belongs to this skill. It tests
  that the description, not a keyword, decides the route. Never names the
  skill.
expected_outcome: Routes to acs:create-e2e-tests.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The code for TKT-102 is done, so no more implementation work. What's left is the end-to-end layer: script the e2e cases from its test plan as Playwright suites on the branch.
