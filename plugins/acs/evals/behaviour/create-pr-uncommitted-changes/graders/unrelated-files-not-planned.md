---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-pr/iter-1/commit-plan.json }
pattern: '"paths"\s*:\s*\[[^\]]*(?:notes/release-plan\.md|src/shop/pagination\.py)'
match: not_contains
---

No group of the confirmed plan carries the user's note (dirty before the run:
`excluded`, never committed) or the WIP file no step recorded (`left_out`,
committed only if the user moves it into a group -- and this user approved the
plan as proposed). Only groups have a `paths` key; the `left_out` and
`excluded` lists that name both files are plain arrays.
