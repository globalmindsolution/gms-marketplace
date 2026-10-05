---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/code/iter-1/filemap.json }
pattern: '"src/shop/cursor\.py"'
---

The declared map is what the file-map guard enforces: if the new module is
missing here, `/acs:code`'s implementer would be denied the file the user
asked for.
