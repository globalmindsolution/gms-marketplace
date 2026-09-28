---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-2/ticket.json }
pattern: '"doc_set"\s*:\s*"standards"'
---

The one eligible set got its own delivery ticket through `acs step start
--doc-set standards --allocate`: the next id after the in-flight EVAL-1,
recording its set.
