---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/review-code/state.json }
pattern: 'iteration-\d+ verdict: [1-9]\d* blocking finding'
---

Not the review's claim -- the kernel's. `post-review-code.py` derives
`verifier_passed` from `iter-<n>/verdict.json` and records its provenance as
"iteration-<n> verdict: <k> blocking finding(s)" only when the verdict
VALIDATES (skill, run, iteration, reviewed_sha, every finding's id, evidence
and resolved_when, and `passed` agreeing with the findings) and carries at
least one blocking finding. A missing, malformed or self-contradicting verdict,
a pass, or a review never finished through the post-hook all fail here.
