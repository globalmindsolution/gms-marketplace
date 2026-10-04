---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:audit-security.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

I think someone committed credentials at some point. Check the repo for leaked API keys, passwords, tokens and private keys, plus any insecure configuration, and tell me where each one is -- without printing the values.
