# Messaging — the `<task>`/`<result>` wire, the fan-out and how a subagent is spawned

Read this before the first subagent spawn of a run: every message you send
and receive follows these rules.

Messaging rules (`the SubagentStop hook's message check`):

- Send each subagent one `<task skill="create-api-contract"
  phase="contract-author|gap-analyst|contract-reviewer" ticket-id="<id>"
  iteration="n">` with `<objective>`, `<inputs>` (file refs) and
  `<constraints>` — always `partition`, `architecture_dir`, `feature`,
  `lld_types` (the owned type, `api-contract`), `required_sections` (the
  interface document's six headings, SKILL.md's Output contract) and
  `audience_style_profile` (`integrators (precise shapes + examples)`); a
  writer slice adds `slice_scope`, a reviewer slice `dimensions`, a gap
  analyst `interface`.
- A sliced instance's task carries its slice id,
  `<task skill="create-api-contract" phase="contract-reviewer" slice="trace" …>`,
  and its `<result … slice="trace" …>` echoes it, so the SubagentStop snapshot
  lands at `iter-<n>/<phase>-<slice>-message.xml` and parallel results never
  overwrite each other. Slice ids are letters, digits and `-`; `survey`,
  `write`, `integration` and `preamble` are reserved for the roles SKILL.md
  names. A single, un-sliced instance omits `slice`.
- Validate EVERY message you send and receive — the SubagentStop hook checks
  each returned `<result>`'s `skill=`, `phase=` and `iteration=`. On invalid:
  re-request once with the validation error quoted; still invalid → fail the
  run and record the error in the result document's `errors`.
- Every phase output is persisted at the phase boundary, BEFORE the next phase
  starts: the SubagentStop hook snapshots each returned message; if that
  snapshot is missing (a host that does not fire the hook), write the `<task>`
  and `<result>` there yourself.
- Spawn each role with the Agent tool under the name in
  `context.agents.<role>` — the plugin's `acs:create-api-contract-<role>`
  (`acs:create-api-contract-contract-author`,
  `acs:create-api-contract-gap-analyst`,
  `acs:create-api-contract-contract-reviewer`), or the generated
  `acs-create-api-contract-<role>` copy `acs step start` wrote where
  `settings.models` sets a model or effort for it; fall back to the
  un-namespaced name only if the runtime rejects the namespaced one. Model and
  effort travel with that agent, so pass none of your own. If the runtime
  rejects the agent, FAIL the run with that exact error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input. If the runtime moves the agent to the background anyway, wait for
its completion notification — never poll with `sleep` loops (`for i in $(seq 1
40); do sleep 15; done` and its kin), which wait a fixed ten minutes whatever
the agent did.

**Fan-out rules.** The parallel instances of a phase are spawned in ONE
message — one Agent call per slice, each `run_in_background: false` — and you
wait for every one before the join. Cap: at most `settings.parallel.max_agents`
(default 4) per message; beyond it, waves of that size, the next phase only
after the last wave. The join is a command, never prose:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/create-api-contract/iter-<n>/<joined>.md <slice files…>
```

A joined file is always rebuilt from its slice files, never edited by hand.
