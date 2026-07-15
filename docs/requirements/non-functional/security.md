# Security

Quality requirements constraining how the plugin handles credentials and
subagent blast radius. Moved out of `configuration.md`'s "Secrets" section
during the MAR-145 functional/non-functional reorg (content unchanged).

## Secrets

Credentials for remote trackers MUST NOT be stored in `settings.json`.
Tracker access goes through the official CLIs — `gh` for GitHub and `acli`
for Jira — which manage their own authentication (`gh auth login`,
`acli auth`). `settings.json` holds only non-secret configuration (URLs,
project keys, formats). `/init` and the pre-hooks SHOULD check that the
configured tracker's CLI is installed and authenticated.

## Subagent tool restrictions

Planner/verifier read-only tool allowlists and the executor's no-spawn
restriction are a security-relevant discipline (blast-radius containment);
the full behavioral definition lives in
[../functional/reflection.md](../functional/reflection.md#file-based-state-instead-of-conversation-memory)
(the Grounding paragraph) — cross-referenced here rather than duplicated,
per the functional/non-functional tie-break rule.
