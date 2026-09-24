# Security

Quality requirements constraining how the plugin handles credentials and
subagent blast radius. Moved out of `configuration.md`'s "Secrets" section
during the MAR-145 functional/non-functional reorg (content unchanged).

## Secrets

Credentials for remote trackers MUST NOT be stored in `settings.json`.
Tracker access goes through the official CLIs — `gh` for GitHub and `acli`
for Jira — which manage their own authentication (`gh auth login`,
`acli auth`). `settings.json` holds only non-secret configuration (URLs,
project keys, formats). `/setup` and the pre-hooks SHOULD check that the
configured tracker's CLI is installed.

## Subagent tool restrictions

Planner/verifier read-only tool allowlists and the executor's no-spawn
restriction are a security-relevant discipline (blast-radius containment);
the full behavioral definition lives in
[../functional/reflection.md](../functional/reflection.md#file-based-state-instead-of-conversation-memory)
(the Grounding paragraph) — cross-referenced here rather than duplicated,
per the functional/non-functional tie-break rule.

## Transcripts are not read

acs reads no Claude Code transcript: nothing in the plugin opens a session
`.jsonl` file or its `subagents/` subtree, and no transcript text or figure
is persisted into the workspace store. The only Claude Code input a hook
reads is its own hook envelope on stdin. The token measurement that once
read a run's transcript was removed with usage recording
([ADR 0104](../../adr/0104-no-usage-dashboards-no-usage-recording.md)).
