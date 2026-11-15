---
type: regex
target: { source: file, path: docs/development/customer-listing/EVAL-1/analysis/customer-listing.md }
pattern: '^## Impact map[ \t]*$(?:(?!^## )[\s\S])*src/shop/__init__\.py'
flags: m
---

The impact map lives in the context file -- `customer-listing.md`, the one
bounded context the prompt names -- and is derived from the CODE:
`list_customers` lives in `src/shop/__init__.py`, and the map's first column
is a repo-relative path. An analysis that paraphrases the ticket without
surveying the repo, or that keeps its impact map out of the context file,
fails.
