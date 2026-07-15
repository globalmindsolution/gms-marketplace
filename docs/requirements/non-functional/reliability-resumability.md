# Reliability & resumability

Quality requirements for surviving crashes, interruptions, and deliberate
handoffs without losing pipeline state. This is a cross-reference file, not
a duplicate: the full behavioral definition of resume/handoff/reconcile
already lives in the functional files below (moved wholesale, content
unchanged), per the functional/non-functional tie-break rule
(genuinely-both content stays in its functional home with a one-line
pointer here rather than being copied).

- [../functional/workflow.md](../functional/workflow.md#resuming-a-ticket) —
  resume at three levels (between steps, within `/ship`, mid-skill
  reconcile).
- [../functional/workflow.md](../functional/workflow.md#session-handoff) —
  deliberate session handoff (flush, mark, release, take over).
- [../functional/workspace-and-state.md](../functional/workspace-and-state.md#lifecycle) —
  archived-partition lifecycle.
- [../functional/workspace-and-state.md](../functional/workspace-and-state.md#concurrency--parallel-tickets) —
  re-entrant `.lock` locking.
