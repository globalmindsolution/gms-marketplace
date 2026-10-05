---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/code/iter-1/filemap.json }
pattern: '"src/shop/__init__\.py"'
---

The file map is DECLARED through `acs.py filemap set --skill code --iteration
1`, which writes this file -- the map `/acs:code`'s first implementers are
checked against.
