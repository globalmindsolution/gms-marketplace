---
description: >-
  Borrows the vocabulary of /acs:create-test-docs on purpose -- it mentions
  deriving test cases from the acceptance criteria -- while the request
  still belongs to this skill. It tests that the description, not a keyword,
  decides the route. Never names the skill.
expected_outcome: Routes to acs:create-api-contract.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Before we derive any test cases for TKT-83, the request and response shapes and error codes of its new /payouts/batch endpoint need pinning down, traced to the acceptance criteria.
