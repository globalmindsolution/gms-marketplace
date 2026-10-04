---
type: regex
target: { source: file, path: .git/logs/refs/heads/main }
pattern: '\tcommit \(initial\): shop 2\.4\.0\n$'
---

main's own reflog still ends at its only commit: no doc fix landed on main.
