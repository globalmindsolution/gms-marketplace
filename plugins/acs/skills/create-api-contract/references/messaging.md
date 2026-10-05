# Messaging — the `<task>`/`<result>` wire and how a subagent is spawned

Read this before the first subagent spawn of a run: every message you send
and receive follows these rules.

Messaging rules (`the SubagentStop hook's message check`):

- Send each subagent one `<task skill="create-api-contract"
  phase="contract-author|contract-reviewer" ticket-id="<id>" iteration="n">` with
  `<objective>`, `<inputs>` (file refs) and `<constraints>` — always
  `required_sections` (the seven headings below), `audience_style_profile`
  (`integrators (precise shapes + examples)`), and `contracts_mode` (the mode
  resolved above).
- A sliced instance's task carries its slice id,
  `<task skill="create-api-contract" phase="contract-reviewer" slice="trace" …>`,
  and its `<result … slice="trace" …>` echoes it, so the SubagentStop snapshot
  lands at `iter-<n>/<phase>-<slice>-message.xml` and parallel results never
  overwrite each other. A single, un-sliced instance omits `slice`.
- Validate EVERY message you send and receive — the SubagentStop hook checks
  each returned `<result>`'s `skill=`, `phase=` and `iteration=`. On invalid:
  re-request once with the validation error quoted; still invalid → fail the
  run and record the error in the result document's `errors`.
- Every phase output is persisted at the phase boundary, BEFORE the next phase
  starts: the SubagentStop hook snapshots each returned message to
  `steps/create-api-contract/iter-<n>/<phase>-message.xml` (`<phase>` is the
  role); if that snapshot is missing (a host that does not fire the hook),
  write the `<task>` and `<result>` there yourself.
- Spawn subagents with the Agent tool: `subagent_type:
  "acs:create-api-contract-contract-author"` and
  `"acs:create-api-contract-contract-reviewer"` — fall back to the
  un-namespaced name (`create-api-contract-contract-author`,
  `create-api-contract-contract-reviewer`) only if the runtime rejects the
  namespaced one. Spawn each role under the name in
  `context.agents.<role>` — the plugin's `acs:create-api-contract-<role>`, or the
  generated `acs-create-api-contract-<role>` copy `acs step start` wrote where
  `settings.models` sets a model or effort for it. Model and effort travel with
  that agent, so pass none of your own. If the runtime rejects the agent, FAIL
  the run with that exact error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.
