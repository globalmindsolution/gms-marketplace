---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"title"\s*:\s*"Amend PRD: [^"]+"'
---

Amend mode with a usable request: the PRD was found, so Start allocates with
`--title "Amend PRD: <summary>"` instead of the built-in "Product definition
(PRD)", and the branch slug follows the title.
