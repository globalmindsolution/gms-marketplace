---
type: regex
target: { source: file, path: .gitignore }
pattern: '^\.acs/\n\*\.pyc\n$'
---

The broad rule is the user's configuration to decide: setup relays the
warning and never fixes it for them -- no `!.acs/` negation, no narrowed
rule, no appended line.
