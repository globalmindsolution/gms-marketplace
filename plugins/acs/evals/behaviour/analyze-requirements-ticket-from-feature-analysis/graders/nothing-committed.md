---
type: regex
target: { source: file, path: .git/logs/HEAD }
pattern: '\tcommit: Customer listing discovery analysis\n$'
---

HEAD's reflog still ends at the scaffold's last entry: the run made no
commit, and created, switched, reset or stashed nothing (ADR-0127).
