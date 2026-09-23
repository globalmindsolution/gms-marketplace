# Portability

Quality requirements for running `acs` across different consumer repos and
users. Moved out of `overview.md`'s Goal 5 and the "Workspace isolation"
Core-principle row during the MAR-145 functional/non-functional reorg
(content unchanged); the detailed configuration mechanics live in
[../functional/configuration.md](../functional/configuration.md).

- **Portability**: the plugin MUST be configurable per user and per project
  via `settings.json` files — the project file seeded with the conventions by
  `/setup`, everything else edited by hand
  (see [../functional/configuration.md](../functional/configuration.md)).

| Core principle | Requirement |
|----------------|-------------|
| Workspace isolation | All skill/hook reads and writes go to `<workspace>/<repo>/<ticket-id>/…`. `<workspace>` is always in-repo, main-checkout-anchored (`.acs/state-machine/`, gitignored), resolving to the same location from every worktree, with no override — so worktrees and parallel tickets across any number of consumer repos are supported (ADR-0086, [ADR-0102](../../adr/0102-documents-are-found-not-configured.md)). |

**Read-outside-the-workspace exception (MAR-1, ADR 0082).** Cost/time
measurement is the one place acs reads outside both the consumer repo and
its own workspace store: the Claude Code transcript directory
(`~/.claude/projects/`). The read is scoped strictly to the exact
`transcript_path` recorded on the run entry (captured from the genuine
`PreToolUse(Skill)` hook envelope, never a constructed path) plus that
session's own `subagents/` subtree — never a sibling session's directory,
never the whole transcript tree. Nothing is written there; the measured
figures are persisted into the workspace store as usual.
