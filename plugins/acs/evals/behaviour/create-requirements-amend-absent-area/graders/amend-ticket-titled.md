---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"title"\s*:\s*"Amend requirements: [^"]+"'
---

Amend mode with a usable request: the set is already populated, so Start
allocates with `--title "Amend requirements: <summary>"` instead of the
built-in "Product requirements doc set".
