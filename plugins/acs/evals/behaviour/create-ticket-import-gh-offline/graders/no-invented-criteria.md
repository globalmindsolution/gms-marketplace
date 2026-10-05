---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"acceptance_criteria"\s*:\s*\[\s*"'
match: not_contains
---

The ticket's content comes from the remote issue. With the pull failed there
is nothing to seed it from, so the allocated placeholder keeps its empty
criteria; criteria written anyway were guessed. (The file must exist, so a
run that never allocated fails here too.)
