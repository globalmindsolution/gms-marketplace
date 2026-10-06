---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?create-tech-design"'
min: 1
---

The run must invoke `acs:create-tech-design` -- the admission under test is the skill's own pre-hook, which fires on that Skill call, and the design must be the skill's, not a hand-written file.
