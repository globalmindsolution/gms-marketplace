---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-pr.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-64's Kafka consumer changes pass the verifier and the code review. Send the branch up for human review: a pull request against the default branch, its body built from the ticket.
