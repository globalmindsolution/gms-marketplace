---
type: regex
target: trace
pattern: '^(?:(?!"name":"Skill","input":)[\s\S])*"name":"Skill","input":\{"skill":"(?:[\w-]+:)?create-design"'
---

Passes when the FIRST Skill call in the run names `acs:create-design`, bare or
plugin-qualified. The run has 3 turns, so looking at the repo before routing
is not a miss; a first Skill call to any other skill, or none at all, is. Later
Skill calls -- a skill invoking its own steps or legs -- are not graded.
