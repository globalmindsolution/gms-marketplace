# 0108 — Nothing about the eval suite runs in CI

**Status**: Accepted · **Date**: 2026-09-24

**Extends**: [0022](0022-behavioral-evals-local-only-ci-runs-no-llm-calls.md),
which kept the paid evals out of CI.

## Context

ADR-0022 kept `claude plugin eval` out of CI because every case spawns a paid
session. The eval suite still reached CI another way: its free checks lived in
`tests/acs/` as `test_*.py`, so `unittest discover -s tests` ran them on every
PR. Those were the case-shape and coverage check (`test_eval_cases.py`), the
gate's own test (`test_eval_gate.py`), grader calibration
(`test_eval_grader_calibration.py`), and four probe-expectation classes buried
in per-ticket doc tests. Several CI doc tests also read the case files just to
get a count.

That tied every eval-suite edit to the CI run of every PR. An eval case change
could turn an unrelated PR red. The calibration check, which builds scaffolds
and drives the plugin's CLIs, ran on every PR whether or not the PR touched
anything it covers. The maintainer's decision is that CI does not do evals.

## Decision

**CI runs nothing that reads the eval suite.**

- The free checks move to `tests/evals/`, named `check_*.py`. CI's
  `unittest discover -s tests` loads only `test*.py`, and the directory is not
  a package, so CI never imports them. The four probe-expectation classes
  (create-docs, standardize-project, run-e2e-tests, setup), the testing
  strategy's derived artifact-coverage claim, and the rename sweep's one
  eval-file entry move with them into `check_probe_expectations.py`.
- The strict case reader moves to `tests/evals/eval_cases.py`. No test under
  `tests/acs/` imports it. The doc tests that pinned the routing-coverage count
  now derive it from the shipped skills; that every shipped skill has a
  routing case is asserted locally, by `check_cases.py`.
- **The checks run locally, in two places:**
  - The `acs-eval-checks` pre-commit hook fires when a commit touches the
    suite, a skill, the hook scripts, the schemas or the gate.
    `.github/workflows/security.yml` sets `SKIP: acs-eval-checks` on its
    pre-commit job.
  - The release gate's first step.
- The CI invariant grep gains `tests/evals`:
  `grep -rn "run_evals\|evals/behavioural/\|plugin eval\|tests/evals"
  .github/workflows/` must return nothing.

**The cases a change affects run locally, on the team's subscription.** The
`acs-evals` hook (`scripts/eval_changed.py`) runs at the `pre-push` and
`manual` stages. CI's pre-commit job runs neither, and the script exits when
`CI` is set. It works like this:
- It selects the cases the branch's diff can move and runs each three times.
- It applies the release gate's rules (ADR-0107) to the skills the change
  touches:
  - a `negative` or `control` misroute in any run blocks the push;
  - so does a touched skill whose selected description cases route less than
    2/3 of their pooled runs;
  - so does a run that could not happen, including a gated case the budget
    guard stopped before it ran.
- Explicit and behaviour cases are reported, not blocking.
- Runs draw on the Claude subscription `claude` is logged in with, so the hook
  is on by default (`git config acs.evals false` turns it off). The budget is a
  runaway guard on the CLI's computed cost, $25 per push, not a bill. Without
  `claude` installed, it lets the push through.
- It never passes `--trust-plugin`: the CLI remembers trust per directory, and
  the developer confirms it once in a terminal.

## Consequences

**A malformed eval case can now reach `main`.** CI will not stop it. The
pre-commit hook stops it only for contributors who ran `pre-commit install`.
Otherwise the first thing to catch it is the release gate's free step, which
still fails before anything is paid for. That is the trade this decision
accepts.

**The pre-commit hook is the day-to-day guard,** so it is scoped to be cheap:
it runs only when the commit touches something the checks read, and takes a
few seconds.

**Coverage is measured without the calibration check.** Its subprocess runs of
`acs.py` no longer count toward CI's coverage floor. The floor still holds.

**Doc tests keep checking the docs.** A doc that states the routing-coverage
count is still pinned in CI, to the shipped-skill count rather than to the case
files.
