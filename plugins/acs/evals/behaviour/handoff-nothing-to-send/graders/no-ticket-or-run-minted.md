---
type: regex
target: files
pattern: '^\.git/acs/state-machine/example-shop/(runs/|[A-Z]+-\d+/)'
flags: m
match: not_contains
---

Nothing to send is not a reason to make something to send: a run that mints a
ticket or starts a run so it has a package fails here.
