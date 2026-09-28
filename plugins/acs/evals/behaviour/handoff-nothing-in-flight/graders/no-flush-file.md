---
type: file_exists
path: '**/handoff-context.md'
exists: false
---

Step 2: with no step in flight, Step 3 is skipped -- there is no in-flight
phase to flush. And `handoff.py` writes its own run-root
`handoff-context.md` only when it finalized a step. So any
`handoff-context.md` means the run invented a flush, or started a step and
handed THAT off.
