---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements/result.json }
pattern: '"docs/'
match: not_contains
---

A local document is not a repo change: `states.files` (what /acs:create-pr
commits, ADR-0127) names no docs/ path. The file must exist -- a run that
never finished fails here too.
