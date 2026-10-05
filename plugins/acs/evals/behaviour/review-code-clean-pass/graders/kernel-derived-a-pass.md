---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/review-code/state.json }
pattern: 'iteration-\d+ verdict: 0 blocking finding'
---

Not the review's claim -- the kernel's. `post-review-code.py` derives
`verifier_passed` from `iter-<n>/verdict.json` and records "iteration-<n>
verdict: 0 blocking finding(s)" only for a verdict that validates and carries
no blocking finding. A review that invented a blocking finding, wrote an
unusable verdict, or never finished through the post-hook fails here. The
fixture's tests use pytest, so stage 3 needs pytest and a coverage tool on the
host: without them the gate is correctly a blocking `gate` finding and this
grader fails -- run the case where they are installed.
