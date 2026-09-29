---
type: regex
target: { source: file, path: docs/tickets/EVAL-1/analysis.md }
pattern: '^## Impact map[ \t]*$(?:(?!^## )[\s\S])*src/shop/__init__\.py'
flags: m
---

The impact map is derived from the CODE: `list_customers` lives in
`src/shop/__init__.py`, and the map's first column is a repo-relative path.
An analysis that paraphrases the ticket without surveying the repo fails.
