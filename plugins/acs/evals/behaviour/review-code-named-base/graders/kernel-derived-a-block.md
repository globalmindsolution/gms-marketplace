---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/review-code/state.json }
pattern: 'iteration-\d+ verdict: [1-9]\d* blocking finding'
---

Not the review's claim -- the kernel's. `post-review-code.py` records this
provenance only when the verdict VALIDATES and carries at least one blocking
finding. A missing or malformed verdict, a pass, or a review never finished
through the post-hook all fail here.
