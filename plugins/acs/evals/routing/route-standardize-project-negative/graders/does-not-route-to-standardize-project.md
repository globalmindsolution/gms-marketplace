---
type: regex
target: trace
pattern: '^(?:(?!"name":"Skill","input":)[\s\S])*"name":"Skill","input":\{"skill":"(?:[\w-]+:)?standardize-project"'
match: not_contains
arm: both
---

Passes unless the FIRST Skill call in the run names the internal leg
`acs:standardize-project`, bare or plugin-qualified. The entry point dispatching the leg later
is the correct route, and the tempered pattern cannot see past the first call.
