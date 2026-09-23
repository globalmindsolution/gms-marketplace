---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  It names the ticket on purpose: an earlier wording said "this epic" and
  named none, and the model identified the right skill and then declined for
  want of a referent ("I need to know which epic you mean"). KNOWN CONFOUND:
  the prompt presupposes an epic ticket TKT-1 that is genuinely design-
  significant, and the case runs in an empty workspace. Past misses came
  from the context, not the description -- seed an epic before reading a
  miss here as a description defect.
expected_outcome: Routes to acs:create-design.
tags: [routing, description]
max_turns: 10
allowed_tools: [Skill]
---

TKT-1 is design-significant. Settle its system design and weigh the options before anyone writes code.
