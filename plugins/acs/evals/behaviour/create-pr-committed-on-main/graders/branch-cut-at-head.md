---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: 'checkout: moving from main to task/EVAL-1'
---

The work was committed on main. create-pr's plan reports it as `ahead` and
`acs.py pr commit` with no groups cuts the plan's branch at HEAD -- the reflog
records that switch. A run that left HEAD on main, or recreated the commit with
raw git, has no such entry.
