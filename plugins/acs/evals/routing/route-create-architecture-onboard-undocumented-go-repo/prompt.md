---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-architecture.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

We are bringing acs onto an existing Go payments repo that has no design docs at all. Reverse-engineer its structure from the source and the PRD into Mermaid C4 diagrams and low-level flows.
