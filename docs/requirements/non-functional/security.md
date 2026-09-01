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
configured tracker's CLI is installed and authenticated.

## Subagent tool restrictions

Planner/verifier read-only tool allowlists and the executor's no-spawn
restriction are a security-relevant discipline (blast-radius containment);
the full behavioral definition lives in
[../functional/reflection.md](../functional/reflection.md#file-based-state-instead-of-conversation-memory)
(the Grounding paragraph) — cross-referenced here rather than duplicated,
per the functional/non-functional tie-break rule.

## Transcript privacy boundary (MAR-1, ADR 0082)

Cost/time measurement reads the Claude Code transcript for a run's own
recorded `transcript_path` plus its `subagents/` subtree. The boundary is
structural, not merely a policy note: only `*.jsonl` files are ever
enumerated or opened, so `subagents/*.meta.json` sidecars — which carry a
free-text `description` field — are never opened at all, eliminating that
free-text surface from exposure by construction rather than by convention.
Within each `*.jsonl` record, only the four integer `message.usage` token
fields, `message.model`, `timestamp`, and the attribution fields
(`attributionSkill`/`attributionAgent`) are ever read. `message.content`,
prompt text, and tool results are never read, and no transcript text of any
kind is ever persisted into the workspace store — `usage_reader.py` itself
persists nothing; it returns a dict of integer counts bucketed by role
(`role_usage`) and by model (`model_usage`, MAR-3) to its caller.
`acs_lib.py`'s `_measure_run_usage`/`finalize_run` are what persist that
returned data into the run entry; `cost_sampler.py` persists only a float,
a key-path string, and an ISO timestamp. No network calls occur anywhere
in the measurement path.
