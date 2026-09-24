---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '\(ticket under analysis\)'
match: not_contains
---

The executor rewrote the placeholder title the allocate step writes. The
file must exist for this to pass -- a regex grader whose file is missing
fails in every match mode -- so it cannot pass on a run that minted nothing.
