---
description: >-
  Borrows the vocabulary of /acs:create-test-docs on purpose -- it talks
  about test cases being derived and traced -- while the request still
  belongs to this skill. It tests that the description, not a keyword,
  decides the route. Never names the skill.
expected_outcome: Routes to acs:create-e2e-tests.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

TKT-94's test cases are already derived and traced — leave test-cases.md alone. Take the three e2e rows in it and turn them into actual end-to-end test code.
