---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  It names a ticket rather than "the changes on this branch": that first
  wording presupposed a branch with changes the empty workspace lacks, and a
  trace showed the model searching for a git tool before routing -- it
  routed on 1 of 2 runs. The ticket-id form is the one route-code uses, and
  review-code accepts a ticket id. Note a realistic competitor: when
  acs:review-code's gate refused for want of settings, the model fell back
  to a non-acs `code-review` skill present in the session. The grader does
  not count that -- `code-review` does not match `review-code"` -- which is
  the point.
expected_outcome: Routes to acs:review-code.
tags: [routing, description]
max_turns: 10
allowed_tools: [Skill]
---

TKT-1's implementation is finished. Check it over before it goes up for a PR — build, lint and the full test suite included.
