---
type: regex
target: { source: file, path: docs/architecture/lld/customer-listing/EVAL-1/api-contract.md }
pattern: '^-{3}\n(?:[a-z_]+:[^\n]*\n)*items:[ \t]*[1-9]\d*[ \t]*\n(?:[a-z_]+:[^\n]*\n)*-{3}'
---

The front matter's `items` is the number of `### ` items under `## Surface`;
this ticket has at least one (GET /customers), so it is a positive integer in
the front matter block that `front_matter_check.py` parses.
