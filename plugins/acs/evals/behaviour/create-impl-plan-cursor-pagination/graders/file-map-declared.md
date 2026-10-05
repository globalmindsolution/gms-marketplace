---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/code/iter-1/filemap.json }
pattern: '"src/shop/__init__\.py"'
---

The plan's file map is DECLARED through `acs.py filemap set --skill code
--iteration 1 --task <k> --file ...`, which writes this file: it is the map
`/acs:code`'s first implementers are checked against, and an undeclared map
means no enforcement at all. The run id is the ticket id.
