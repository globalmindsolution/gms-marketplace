---
type: regex
target: { source: file, path: .git/config }
pattern: '\[branch "task/EVAL-1-product-quality-doc-set"\]\s+remote = origin'
---

The delivery branch (`{type}/{ticket_id}-{slug}`) was pushed with
`git push -u origin`, which writes this upstream section only on success. The
skill pushes only after its reviewer passes.
