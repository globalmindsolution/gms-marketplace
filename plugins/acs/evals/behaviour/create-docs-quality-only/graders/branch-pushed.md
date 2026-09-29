---
type: regex
target: { source: file, path: .git/config }
pattern: '\[branch "task/EVAL-1-[^"]+"\]\s+remote = origin'
---

The set's delivery branch (`{type}/{ticket_id}-{slug}`, EVAL-1 being the one
ticket this run mints) was pushed with `git push -u origin`, which writes this
upstream section only on success. The skill pushes only after the set's
reviewer passes.
