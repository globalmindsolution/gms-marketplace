---
type: regex
target: { source: file, path: .git/config }
pattern: '\[branch "task/EVAL-1-[^"]+"\]\s+remote = origin'
---

The delivery branch (`{type}/{ticket_id}-{slug}`, the first ticket minted
under prefix EVAL) was pushed with `git push -u origin`: git writes the
upstream section into `.git/config` only when that push succeeds. The branch's
slug is rendered by the model, so only its prefix is pinned.
