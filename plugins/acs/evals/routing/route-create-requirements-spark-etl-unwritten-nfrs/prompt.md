---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-requirements.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

A post-mortem found our Spark ETL jobs have latency and retention expectations nobody wrote down. Refresh the requirements set so those non-functional items exist, grounded in the pipeline code.
