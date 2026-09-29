---
description: >-
  Borrows the vocabulary of /acs:merge-pr on purpose -- it talks about
  merging and a PR's readiness -- while the request still belongs to this
  skill. It tests that the description, not a keyword, decides the route.
  Never names the skill.
expected_outcome: Routes to acs:release.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't merge anything, I'll do that myself. Just get 1.8.0 ready: compose its changelog section from the merged tickets, bump the version refs, and open the PR.
