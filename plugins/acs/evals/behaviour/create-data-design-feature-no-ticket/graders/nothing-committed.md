---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: Architecture set: HLD and the LLD index\n$'
---

HEAD's reflog still ends at the scaffold's last entry: the run made no
commit and created, switched, reset or stashed nothing. The documents stay
local for the user to review (ADR-0126, ADR-0127).
