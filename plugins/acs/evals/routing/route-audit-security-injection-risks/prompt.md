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

Find every place in this repo where user input can reach a SQL query, a shell command or a template without being escaped or bound. Injection risks only, each with the file and line and how an attacker would use it.
