---
description: >-
  Borrows the vocabulary of /acs:docs-sync on purpose -- it is about docs
  that drifted from what landed -- while the request still belongs to this
  skill. It tests that the description, not a keyword, decides the route.
  Never names the skill.
expected_outcome: Routes to acs:release.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

The CHANGELOG has drifted behind what we've merged since 2.4.0. Write the 2.5.0 section from the merged-ticket archive and bump the version files for the cut.
