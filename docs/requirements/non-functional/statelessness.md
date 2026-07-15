# Statelessness

Quality requirements keeping the coordinator free of in-memory conversation
state between pipeline steps. Moved out of `overview.md`'s Goal 6 and the
"File-based state" Core-principle row during the MAR-145 functional/
non-functional reorg (content unchanged).

- **Stateless orchestration**: the coordinator MUST NOT rely on conversation
  history between workflow steps; all inter-step knowledge is persisted as
  JSON files in the workspace (see
  [../functional/workspace-and-state.md](../functional/workspace-and-state.md)).

| Core principle | Requirement |
|----------------|-------------|
| File-based state | Subagents write states, findings, error details, and stop reasons into JSON files in the workspace; the coordinator stays stateless between steps. |

The detailed statelessness-between-steps mechanics (persistence at each
phase boundary, resumability) live in
[../functional/workflow.md](../functional/workflow.md#statelessness-between-steps)
— cross-referenced here rather than duplicated, per the functional/
non-functional tie-break rule.
