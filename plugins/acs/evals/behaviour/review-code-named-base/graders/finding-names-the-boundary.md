---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/review-code/verdict.json }
pattern: 'can_checkout|age\s*>=?\s*(?:18|ADULT_AGE)|boundary|off[- ]by[- ]one|aged 18|exactly 18|18-year-old|18 or over'
flags: i
---

The ticket's own defect: `can_checkout` uses `age > 18`, so an 18-year-old --
whom AC-1 admits -- is refused. The changeset's tests check 30 and 12 only, so
the defect is in the diff and the criteria, not in a red test.
