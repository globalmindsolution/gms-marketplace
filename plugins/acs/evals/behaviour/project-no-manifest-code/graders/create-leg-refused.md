---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-project/result.json }
pattern: '"dimension"\s*:\s*"greenfield"'
---

The table's `bootstrap` verdict dispatched create-project, and its own
greenfield gate refused through its mandatory Finish: a blocking finding with
`dimension: "greenfield"` listing the files it found. An umbrella that never
dispatched, or dispatched standardize-project instead, has no such file.
