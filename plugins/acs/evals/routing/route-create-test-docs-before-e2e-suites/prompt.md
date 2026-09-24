---
description: >-
  Borrows the vocabulary of /acs:create-e2e-tests on purpose -- it mentions
  end-to-end suites -- while the request still belongs to this skill. It
  tests that the description, not a keyword, decides the route. Never names
  the skill.
expected_outcome: Routes to acs:create-test-docs.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Before anyone writes end-to-end suites for TKT-18, derive the full set of test cases from its acceptance criteria and trace each one.
