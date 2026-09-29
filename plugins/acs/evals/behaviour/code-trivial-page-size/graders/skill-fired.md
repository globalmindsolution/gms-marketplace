---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?code-trivial"'
min: 1
---

The leg, not the entry point. The prompt asks for /acs:code and never names a
delivery path; the plan's `## Contract` block records `trivial`, and /acs:code
dispatches to `acs:code-trivial` with a real Skill call. A run that stayed in
/acs:code, or picked another leg, did not read the recorded path.
