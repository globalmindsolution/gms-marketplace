---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-test-docs/state.json }
pattern: '"e2e_cases"\s*:\s*[1-9]'
---

`states.e2e_cases` must equal the published front matter -- positive here.
