---
description: >-
  Borrows the vocabulary of /acs:create-docs on purpose -- it names the
  operations runbook -- while the request still belongs to this skill. It
  tests that the description, not a keyword, decides the route. Never names
  the skill.
expected_outcome: Routes to acs:docs-sync.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

No new doc sets needed. TKT-11's branch changed the retry defaults, and the existing operations runbook still documents the old values. Reconcile the docs with that change.
