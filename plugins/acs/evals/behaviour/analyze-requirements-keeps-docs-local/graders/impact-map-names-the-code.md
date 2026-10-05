---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements/local/analysis/customer-listing.md }
pattern: '^## Impact map[ \t]*$(?:(?!^## )[\s\S])*src/shop/__init__\.py'
flags: m
---

Kept local is still the full analysis: the impact map is derived from the
code, and `list_customers` lives in `src/shop/__init__.py`.
