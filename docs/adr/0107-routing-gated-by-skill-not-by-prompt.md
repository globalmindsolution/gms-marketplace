# 0107 — Routing is graded on the first move and gated by skill, not by prompt

**Status**: Accepted · **Date**: 2026-09-24

**Builds on**: [0022](0022-behavioral-evals-local-only-ci-runs-no-llm-calls.md), which keeps
paid evals out of CI and makes `release.pre_release_gate` the place they run.

## Context

The release gate ran `claude plugin eval plugins/acs --tag routing` with no
`--threshold`. The CLI fails a run when any **case** scores below the
threshold, and the default is 1.0. An audit of the suite found the gate could
not pass, and that a pass would not have meant much if it had:

- **It was unpassable.** It included the eight `explicit` cases. The CLI can
  expand a typed `/acs:<skill>` before any model turn, so no Skill call is made
  for a grader to see, and six of those cases scored 0.00 in the first full
  run. Leaving those aside, routing is stochastic. A skill that routes right 90%
  of the time scores 3/3 on one prompt only 73% of the time.
- **A pass could be wrong.** A routing grader counts Skill calls anywhere in the
  run, and runs had ten turns. `/acs:ship` invokes each step with the Skill
  tool, so a request wrongly routed to `ship` passed a step's case. For the
  same reason, a request correctly routed to `/acs:code` failed a leg's negative
  once `code` dispatched the leg.
- **One prompt per skill** measured one sentence, not a description. No prompt
  tested the neighbours a model actually confuses, and the only unrelated-request
  control was a poem.
- **Some graders could not fail.**
  - `create-ticket-artifacts` passed a run that only started the skill: the
    allocate step writes a placeholder ticket that already satisfied all three
    of its file graders.
  - `resume-and-verify` passed on `/health` appearing in a comment.

## Decision

**A routing run is one turn** (`max_turns: 1`), so only the model's first move
is graded. The CLI passes the limit to the child as `--max-turns` and grades the
trace whatever the exit status. A test pins the limit on every routing case.

**Each skill a user reaches by description has three phrasings.** One is the
plain request, one is an indirect request with its context stated, and one is
`confusable`: it borrows a named neighbour's vocabulary. Controls are requests
answered in prose, including ones next to acs's vocabulary (a git question,
general PR advice). Tests pin all of this.

**The gate judges skills, not prompts.** The CLI runs the `description`,
`negative` and `control` cases with `--threshold 0 --json <file>`, so it
measures and does not judge. Then `scripts/eval_gate.py` applies the policy:

- `negative` and `control` must pass every run.
- For `description` cases, each skill's pooled runs must route at least 2/3 of
  the time, and the suite as a whole at least 9/10.
- `explicit` cases are not gated.
- The script fails closed on a partial run, an unknown result format, an
  unmapped or missing case, or a result older than six hours.

The two rates are **provisional**. They come from arithmetic, not data, and are
to be re-set from the first three-run baseline.

**Free graders are calibrated for free.** `tests/evals/check_grader_calibration.py` (run locally, never in CI — [ADR-0108](0108-evals-never-run-in-ci.md))
works on every `setup/` and `artifacts/` case:
- It builds the case's real scaffold.
- It plays an ideal run and one or more bad runs through the plugin's own
  writers (`setup apply`, `step start --allocate`, `ticket save`, `step finish`).
- It grades them with the CLI's own rules, read out of the CLI: a missing file
  fails a regex grader in every match mode, and only created paths count.
- It requires the ideal run to pass every free grader and each bad run to fail
  at least one.

## Consequences

**Every earlier routing number is history, not a baseline.** The first full run
predates the one-turn limit and 51 of the 90 cases.

**The gate grows from 39 to 82 cases.** Its cost ceiling rises from $20 to $40.
A one-turn run's cost has not been measured.

**A single misroute fails a negative.** That is deliberate. A description that
occasionally pulls a request onto an internal leg is a defect to fix, not noise
to average away.

**The gate depends on the CLI's `--json` format (schema version 1).** A new
version fails the gate, and the script is updated deliberately; it never
silently reads a different shape as a pass. The calibration test mirrors the CLI
2.1.281 grading rules the same way.

**Two checks remain undone and are paid.** One is a sensitivity run showing that
each case scores lower against a deliberately broken plugin. The other is a
judge calibration showing that each `llm` grader agrees with a human. Until both
are done, a pass means "the graders we could check free were checked", not "the
suite is proven". `plugins/acs/evals/README.md` states which is which.
