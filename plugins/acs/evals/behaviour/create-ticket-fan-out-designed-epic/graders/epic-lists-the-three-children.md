---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"children"\s*:\s*\[\s*"EVAL-2"\s*,\s*"EVAL-3"\s*,\s*"EVAL-4"\s*\]'
---

`new-ticket.py --parent EVAL-1` writes BOTH link directions, so the epic's
`children` lists exactly the three minted ids. A run that allocated a new id
first (`--allocate` is not used in this mode) shifts them to EVAL-3..EVAL-5.
