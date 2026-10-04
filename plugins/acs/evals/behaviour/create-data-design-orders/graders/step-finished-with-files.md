---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/steps/create-data-design/state.json }
pattern: '^(?=[\s\S]*"status"\s*:\s*"completed")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/architecture/lld/orders/data/logical-erd\.md")(?=[\s\S]*"files"\s*:\s*\[[^\]]*"docs/architecture/lld/orders/data/physical-schema\.md")'
---

The mandatory Finish ran through `post-create-data-design.py`, which records
the invocation `completed` and persists the result's states. With no ticket
branch checked out nothing is committed, so `states.files` must list every
written path, repo-relative -- it is what /acs:analyze-requirements' publish
commits with the ticket folder. A file written but not recorded is never
committed.
