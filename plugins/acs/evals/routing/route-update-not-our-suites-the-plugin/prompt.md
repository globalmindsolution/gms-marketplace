---
description: >-
  Borrows the vocabulary of /acs:run-e2e-tests on purpose -- it asks to
  check whether anything is broken or stale -- while the request still
  belongs to this skill. It tests that the description, not a keyword,
  decides the route. Never names the skill.
expected_outcome: Routes to acs:update.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Not our test suites: check whether the acs plugin itself is out of date, and if a newer version exists, move to it.
