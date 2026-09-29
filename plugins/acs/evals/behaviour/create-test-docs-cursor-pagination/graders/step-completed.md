---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/runs/EVAL-1/run.json }
pattern: '"create-test-docs":\s*\{[^{}]*"status":\s*"completed"[^{}]*"outcome":\s*"cases_written"'
---

The mandatory Finish ran: result.json carried `outcome: cases_written` and
`post-create-test-docs.py` accepted it, which records both on the run's step
entry. A step left `in_progress`, or a `needs_input` stop over an untraced
criterion, fails.
