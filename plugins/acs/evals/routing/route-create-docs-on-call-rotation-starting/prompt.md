---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:create-docs.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

We start an on-call rotation next month and have nothing written down. The architecture docs are merged, so produce the release process, the incident-response playbook and the observability guide for the service.
