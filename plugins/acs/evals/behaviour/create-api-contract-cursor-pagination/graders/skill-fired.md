---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?create-api-contract"'
min: 1
---

`acs:create-api-contract` must be invoked: a session that edited the interface
document by hand would pass the file graders without the survey, the gap
analysis, the version bump through `acs.py design`, the review or the
post-hook under test.
