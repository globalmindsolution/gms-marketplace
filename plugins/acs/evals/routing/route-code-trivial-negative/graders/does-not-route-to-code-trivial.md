---
type: regex
target: trace
pattern: '^(?:(?!"name":"Skill","input":)[\s\S])*"name":"Skill","input":\{"skill":"(?:[\w-]+:)?code-trivial"'
match: not_contains
arm: both
---

Passes unless the FIRST Skill call in the run names the internal leg
`acs:code-trivial`, bare or plugin-qualified. The entry point dispatching the leg later
is the correct route, and the tempered pattern cannot see past the first call.
