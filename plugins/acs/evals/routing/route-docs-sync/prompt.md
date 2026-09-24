---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  KNOWN CONFOUND: the prompt presupposes a finished code change whose docs
  are now wrong, and the case runs in an empty workspace. That is measured,
  not hypothetical: when an earlier sandbox's diff did not actually change
  documented behaviour, the model read it, judged the docs still accurate,
  and declined to sync -- correctly. It scored 0.67 in the first full run of
  this suite. Seed a change that makes the docs false before reading a miss
  here as a description defect.
expected_outcome: Routes to acs:docs-sync.
tags: [routing, description]
max_turns: 10
allowed_tools: [Skill]
---

The code change is done. Make sure the docs match what actually changed before we raise the PR.
