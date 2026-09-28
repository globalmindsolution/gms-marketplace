# 0113 — Every skill has a behaviour case, graded against a recorded baseline

**Status**: Accepted · **Date**: 2026-09-28

**Builds on**: [0107](0107-routing-gated-by-skill-not-by-prompt.md) and
[0108](0108-evals-never-run-in-ci.md).

## Context

The eval suite graded routing for every shipped skill but behaviour — what a
skill actually writes, records and replies — for two: `setup` (eight cases)
and, through `artifacts/`, `create-ticket` and `code`. A green release gate
said a request reached the right skill, not that the skill did the right
thing. None of the ten behaviour cases had ever run: a behaviour run grants
Bash, Claude Code runs Bash under its OS sandbox, and the cloud container the
suite was built in cannot start it (`apply-seccomp: write /proc/self/uid_map:
Operation not permitted`, no unprivileged user namespaces).

The plugin-evals reference offers a `baseline` grader: a judge decides whether
a run meets the case's criteria at least as well as a reference transcript,
`baseline_file`, a `.jsonl` in the case directory. The CLI refuses a case whose
`baseline_file` does not exist.

## Decision

- **Every shipped skill has at least one behaviour case.** The skills not
  covered by `setup/` or `artifacts/` each get a case under `behaviour/`: a
  scaffold built from a shared fixture (`behaviour/_fixtures/repo.sh`) that
  seeds state only through the plugin's own CLIs; a skill-fired grader; at
  least one free grader on what the skill produced; and a `calibration.py`
  whose ideal play passes every free grader and whose bad plays each fail one.
  `tests/evals/check_cases.py` fails if a shipped skill has no behaviour case.
- **Every behaviour case states its baseline criteria** in
  `baseline.criteria.md` (`PASS if, like the reference, …` / `FAIL if …`),
  including the ten existing cases.
- **A baseline grader arrives only with its transcript.**
  `scripts/record_baseline.py` runs a case once, refuses the run unless every
  grader passed and nothing but the turn limit errored, then writes
  `baseline.jsonl` and `graders/matches-baseline.md` together. A free check
  fails a baseline grader without its transcript, and a transcript without its
  grader.
- **Routing cases take no baseline.** Each keeps its one free grader, so a
  run's score is its routing verdict.
- **Calibration moves beside the case** for `behaviour/`: each case's plays
  live in its own `calibration.py`, so cases can be authored independently.

## Consequences

**The cases are authored and calibrated, not yet run.** Recording needs a host
where Claude Code's Bash sandbox starts — a Mac, or Linux with bubblewrap,
socat and unprivileged user namespaces. Until a case is recorded it is graded
by its free graders and any `llm` grader only.

**A recorded transcript is a real session** and is committed; it is read
before it is committed.

**The behaviour suite is reported, not gated.** `scripts/eval_changed.py`
runs a touched skill's behaviour cases before push and reports them, as it
already did for `setup/` and `artifacts/`. Gating on them waits for their
first recorded baselines and a measured pass rate.

**Skills that need GitHub are graded on their local effect and on how they
fail.** A run has no network or `gh` credentials; a bare repository inside the
run stands in for the remote so pushes work, and the case asserts that a
`gh` failure surfaces as a classified finding (ADR-0088).
