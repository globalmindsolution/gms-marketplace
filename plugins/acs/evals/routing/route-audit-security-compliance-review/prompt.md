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

We're preparing for a SOC 2 compliance review and the assessor will ask how we know the code has no hard-coded secrets and no OWASP Top 10 weaknesses. Produce a severity-ranked security report on the repo; don't change any code.
