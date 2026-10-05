# Spawning — judge slices, the message wire, and the foreground rule

Read this before the first spawn of a run: why the planner runs alone, how
the plan reviewer runs as three judge slices and how their verdicts combine,
the rules every `<task>`/`<result>` follows, and why every spawn waits in
the foreground.

Every fan-out here is yours: spawn the N instances of the SAME agent in ONE
message (all foreground, in the same message), wait for all of them, and join
their outputs before the next phase. At most `settings.parallel.max_agents`
(default 4) instances run per message; beyond that, run the rest in waves of
that size.

**Writer — one planner, never sliced.** `plan.md` is a single document, so
the write is never partitioned. Its survey is not sliced either: the survey IS
the decomposition — one file map whose tasks must be disjoint from each
other, an AC-to-test matrix over every criterion — and that is one judgement
over the whole ticket that per-area slices could only produce in pieces that
collide. With one writer there is no integration pass, and with no survey
slices no synthesis of merged notes.

**Judge slices (every iteration — the default).** The plan reviewer has ten
check dimensions, so it always runs as three slices, each a fresh instance of
`acs:create-impl-plan-plan-reviewer` whose task carries `slice="<id>"` and
`<constraint name="dimensions">` naming the dimension numbers it owns:

| Slice | Dimensions | Owns the run of |
|---|---|---|
| `tests` | 1 acceptance-criteria coverage, 5 test strategy executability | the ONE run of the repo's existing suite command — the `suite` job you started beside the planner, read with `acs.py job wait --name suite` |
| `map` | 4 file-map honesty, 6 design and architecture conformance, 7 scope | the `git ls-files` / `ls` check of every mapped path |
| `document` | 2 completeness, 3 structure (fold only), 8 documentation map, 9 grounding, 10 authoring-conformance | `structure_lint.py` on the fold |

Grounding policing applies in every slice. Spawn the three slices in ONE
message; each writes `iter-<n>/plan-reviewer-<slice>.md`. Join them, in the
table's order, with the `notes merge` command in SKILL.md's Parallelism
section, into the one report every later reader reads.

**De-duplicate after the join.** The slices own disjoint dimensions, so the
merge is the synthesis — but two slices can still report one defect (a mapped
path that does not exist is both a `file-map honesty` and a `grounding`
finding). Drop a finding that cites the same location and the same defect as
another slice's finding, keep the higher severity, and say so in the joined
report: append a `## De-duplicated findings` section to `iter-<n>/plan-reviewer.md`
listing each dropped finding (slice, dimension, location) and the finding it
duplicated (`_None._` when nothing was dropped). Never drop a finding for any
other reason.

**Pass rule for sliced judges:** the iteration passes only if EVERY slice
returned `status="completed"` with zero blocking findings. Any slice's
blocking finding blocks, and all slices' findings — de-duplicated as above,
otherwise verbatim — go to the next planner. A slice that failed or returned no usable result fails the
iteration — never "pass with a missing slice".

Messaging rules (`the SubagentStop hook's message check`):

- Send each subagent one `<task skill="create-impl-plan"
  phase="planner|plan-reviewer" ticket-id="<id>" iteration="n">` — the
  `phase` is the role — carrying `<objective>`, `<inputs>` (file refs) and
  `<constraints>`. The subagent returns a `<result>` with the same `phase` as
  its final content. A plan-reviewer slice's task and result also carry
  `slice="<id>"`; the un-sliced planner omits it.
- Validate EVERY message you send and receive — the SubagentStop hook checks each returned
  `<result>`'s `skill=`, `phase=` and `iteration=` (and `slice=` when sliced).

  On invalid: re-request once with the validation error; still invalid → fail
  the run and record the error in the result document's `errors`.
- Every phase output is persisted at the phase boundary, BEFORE the next
  phase starts: the SubagentStop hook snapshots each returned message to
  `steps/create-impl-plan/iter-<n>/<phase>-message.xml` (a slice's at
  `iter-<n>/<phase>-<slice>-message.xml`); if that snapshot is
  missing (a host that does not fire the hook), write the `<task>` and
  `<result>` there yourself. The roles' own reports are
  `iter-<n>/planner.json` and `iter-<n>/plan-reviewer-<slice>.md`, joined into
  `iter-<n>/plan-reviewer.md` — never write a message over them.
- Spawn subagents with the Agent tool: `subagent_type:
  "acs:create-impl-plan-planner"`, then `subagent_type:
  "acs:create-impl-plan-plan-reviewer"` — fall back to the un-namespaced name
  (`create-impl-plan-planner`, `create-impl-plan-plan-reviewer`) only if the
  runtime rejects the namespaced one. Spawn each role under the name in
  `context.agents.<role>` — the plugin's `acs:create-impl-plan-<role>`, or the
  generated `acs-create-impl-plan-<role>` copy `acs step start` wrote where
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

## Spawning the plan review

Spawn the three `acs:create-impl-plan-plan-reviewer` slices (Judge slices,
above) in ONE message AFTER the draft is written, each with
`<inputs>` of the draft, `requirements.md`, the analysis (`README.md` and its
context files) and `design.md` when they exist, every `<partition>/specs/*.md`, and the repo paths the file map
names; the `tests` slice's `<constraints>` also name the `suite` job (SKILL.md's The
suite job) whose result it reads. The plan reviewer judges fresh — never forward the planner's reasoning —
and each slice writes `steps/create-impl-plan/iter-<n>/plan-reviewer-<slice>.md`,
which you join into `steps/create-impl-plan/iter-<n>/plan-reviewer.md`. The
slices' `<result>` `<findings>` are the verdict: `status="completed"` means
the review RAN, and an empty `<findings>` in every slice is the pass. Never
conclude a pass the plan reviewer did not report — a slice with no usable
result is no pass.
