---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?audit-security"'
min: 1
---

`acs:audit-security` must be invoked: a session that read stats.py by hand and
replied "looks fine" would pass the reply grader without the adjudication,
the report or the result document under test.
