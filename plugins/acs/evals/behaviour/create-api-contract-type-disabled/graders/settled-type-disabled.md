---
type: regex
target: { source: file, path: .git/acs/state-machine/example-shop/runs/EVAL-1/steps/create-api-contract/result.json }
pattern: '"outcome"\s*:\s*"type_disabled"'
---

The skill owns one LLD type, `api-contract`, and design.lld_types drops it:
the run completes as a recorded no-op with `outcome: type_disabled` -- an
answer on the ledger, not a step that silently did not run.
