---
name: test
description: Deprecated alias for /acs:run-e2e-tests, the acs suite runner — kept for one release so existing invocations, scripts and habits keep working. Prefer /acs:run-e2e-tests, which carries the real prose.
---

`/acs:test` was renamed to `/acs:run-e2e-tests` in the skills-independence
refactor, because "test" named a phase rather than the thing this skill does:
run this product's configured suites, write the results artifact, and drive the
regression-ticket loop on a failure. This directory is retained for ONE release
as an alias so existing invocations keep working; `workflows/phases.yaml`
records it under `aliases: {test: run-e2e-tests}`, not in a phase, and
`workflows/ship.yaml` names only `run-e2e-tests`. Do not add behaviour here:
immediately invoke `/acs:run-e2e-tests`, passing every argument you were given
(`--suite <name>`, `--for-ticket <id>`) through unchanged, and let that skill
run — it is the single source of the run mechanics, the results artifact, the
ticket-scoped mode, the ledger write and the closed regression loop. Mention
once, in your first line, that `/acs:test` is deprecated and that
`/acs:run-e2e-tests` is the name to use from now on.

## Completion report (normative)

This alias renders no report of its own: the completion block is the one
`/acs:run-e2e-tests` prints, unchanged, with its own `/acs:run-e2e-tests`
heading — do not re-render, summarize, or relabel it under this skill's name.
