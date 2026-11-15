---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?create-data-design"'
min: 1
---

`acs:create-data-design` must be invoked: a session that wrote an ERD by hand
would pass the file graders without the survey, the version front matter
through `acs.py design`, the review or the post-hook under test.
