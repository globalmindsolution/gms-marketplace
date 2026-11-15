---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/breakdown-ticket/result.json }
pattern: '"converted_from"\s*:\s*"story"'
---

The result document records the split's conversion — `converted_from` is the
type the parent had before the run (`null` on an epic's breakdown).
