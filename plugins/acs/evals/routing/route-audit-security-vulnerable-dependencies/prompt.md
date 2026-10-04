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

Do any of the packages we depend on have known vulnerabilities? Check our manifests and lockfiles with the scanners already installed here, and tell me plainly which ecosystems nothing could check.
