# Portability

Quality requirements for running `acs` across different consumer repos and
users. Moved out of `overview.md`'s Goal 5 and the "Workspace isolation"
Core-principle row during the MAR-145 functional/non-functional reorg
(content unchanged); the detailed configuration mechanics live in
[../functional/configuration.md](../functional/configuration.md).

- **Portability**: the plugin MUST be configurable per user and per project
  via `settings.json` files, and MUST run without any: every key has a
  default ([ADR-0105](../../adr/0105-acs-runs-without-setup.md)). The optional
  `/setup` writes the conventions a team changes; everything else is edited
  by hand (see [../functional/configuration.md](../functional/configuration.md)).

| Core principle | Requirement |
|----------------|-------------|
| Workspace isolation | All skill/hook reads and writes go to `<workspace>/<repo>/<ticket-id>/…`. `<workspace>` is always in-repo, main-checkout-anchored (`.acs/state-machine/`, gitignored), resolving to the same location from every worktree, with no override — so worktrees and parallel tickets across any number of consumer repos are supported (ADR-0086, [ADR-0102](../../adr/0102-documents-are-found-not-configured.md)). |

**No transcript read.** acs does not read the Claude Code transcript
directory (`~/.claude/projects/`); the token measurement that did was removed
with usage recording
([ADR 0104](../../adr/0104-no-usage-dashboards-no-usage-recording.md)).
