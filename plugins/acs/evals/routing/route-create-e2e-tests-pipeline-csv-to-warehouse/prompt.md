---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-e2e-tests.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

The ingestion job for TKT-88 is implemented; test-cases.md calls for two e2e cases that load a CSV and check the warehouse table. We keep e2e suites in tests/e2e — write them there on TKT-88's branch.
