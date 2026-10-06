---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/audit-the-security-of-the-repository-abb3/steps/audit-security/iter-1/report.md }
pattern: '\bdependenc(?:y|ies)\b(?:(?!\b(?:not|never|uncovered|unscanned|no scanners?|cannot|could not)\b)[^\n]){0,80}?\bclean\b|\bno (?:known )?vulnerab\w*(?: \w+){0,2} dependenc'
flags: i
match: not_contains
---

"A category with no scanner and no manual coverage is said to be uncovered,
never reported as clean." A line calling the dependencies clean, or saying
there are no (known) vulnerable dependencies, fails -- nothing checked them.
A line that says they were NOT checked ("uncovered, never clean") does not.
