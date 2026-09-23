---
description: >-
  The explicit command must keep resolving. Previously justified by disable-
  model-invocation ("only an explicit invocation may route"); it now pins
  registration, decided at the init event, alongside the description probe
  that was this skill's negative case.
expected_outcome: Routes to acs:update.
tags: [routing, explicit]
max_turns: 10
allowed_tools: [Skill]
---

/acs:update
