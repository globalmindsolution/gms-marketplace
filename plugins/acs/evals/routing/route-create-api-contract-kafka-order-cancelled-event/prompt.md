---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-api-contract.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

We are about to add an OrderCancelled event to the orders Kafka topic in TKT-61, and the plan is approved. Nail down the message schema, field types, compatibility rules for existing consumers and an example payload.
