---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?create-e2e-tests"'
min: 1
---

`acs:create-e2e-tests` must be invoked: a session that read the case document
itself and wrote nothing would pass the file graders.
