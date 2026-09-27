---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  It names the ticket on purpose: an earlier wording said "this epic" and
  named none, and the model identified the right skill and then declined for
  want of a referent ("I need to know which epic you mean"). It was a known
  confound while the prompt only presupposed an epic that the empty
  workspace lacks; the prompt now states it -- an epic flagged as needing a
  design, with none written yet -- and a routing run is one turn with only
  the Skill tool, so the model can neither go looking for the ticket nor
  find it missing. Re-measured by the next paid run; until then its history
  is a caveat, not a baseline.
expected_outcome: Routes to acs:create-design.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-1 is an epic — multi-currency checkout — and it is flagged as needing a design. None exists yet. Settle its system design and weigh the options before anyone writes the plan.
