---
description: >-
  Borrows the vocabulary of /acs:create-ticket on purpose -- it describes new
  work with no ticket -- while the request is to analyze the requirement it
  states, not to turn it into a ticket. Never names the skill.
expected_outcome: Routes to acs:analyze-requirements.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't open a ticket for this yet. Requirement: shoppers can save a cart and come back to it later from any device. Before anyone plans it, analyze it against our code — what it would touch, what it risks, what is still unclear.
