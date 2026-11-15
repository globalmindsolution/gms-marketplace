---
description: >-
  Borrows the vocabulary of /acs:breakdown-ticket on purpose -- it asks to break a ticket into pieces --
  while the request still belongs to this skill. It tests that the
  description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:create-impl-plan.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

We analysed TKT-73, the nightly Airflow DAG that dedupes customer records, and every open question is resolved. Break it into concrete per-file changes with an executor file map and a test strategy.
