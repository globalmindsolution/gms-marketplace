---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-test-docs.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

The plan for TKT-61, our Kafka-to-BigQuery backfill job, is done. QA wants the traceability written down: each case tied to an AC, typed unit, integration or e2e, with steps and the expected outcome.
