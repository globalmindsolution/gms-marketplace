# 0110 — The routing suite rate is 99/100, measured against a baseline

**Status**: Accepted · **Date**: 2026-09-27

**Amends**: [0109](0109-routing-gate-ten-phrasings-ten-runs.md) (the suite
rate). Ten phrasings per described skill, ten runs a case, the 9/10 per-skill
floor, must-pass negatives and controls, and ADR-0107's one-turn routing runs
all stand.

## Context

ADR-0109 set the suite rate to 1.0: every one of about 2,400 description runs
must route. Tuning the skill descriptions then took the suite from about 80%
to 99.4% (716 of 720 runs in a three-run sweep, with Claude Code's auto-memory
off). Every remaining miss was the model's first move being a look at the repo
— a Glob for the ticket, a search for a shell — before it would have called the
right skill. Further description wording did not move it.

Two ways of grading the route instead of the first move were tried and
measured, and both were worse in the eval sandbox:

- **Three turns, graded on the first Skill call** — 709 of 720. With turns to
  spare, the model looked at the empty workspace, found none of the context the
  prompt described, and answered in prose.
- **Three turns in a scaffolded workspace** — the model investigated for many
  steps without routing, or, finding that the shared fixture lacked what a
  prompt described, told the user the premise was wrong. Satisfying every
  premise would take a bespoke fixture per case.

At a 0.6% miss rate, 2,400 runs miss about 14 times on average. A suite rate
of 1.0 therefore fails every release, whatever the plugin does.

## Decision

- **The suite must route at least 99/100 of its description runs**
  (`--min-suite-rate 99/100`), about 24 misses in 2,400.
- The per-skill floor stays at 9/10, and negatives and controls still must
  pass every run.
- Routing stays graded on the first move, in one turn (ADR-0107).

## Consequences

**The gate passes the measured baseline almost always** — 24 allowed against
about 14 expected — and fails a regression of a few points across the suite, or
any single skill falling below 9/10.

**A first move that looks before routing still counts as a miss.** The rate
absorbs it; it is not redefined away. If a model version makes it common, the
suite rate fails and says so.

**The baseline is one three-run sweep.** The first full ten-run gate run
replaces it; re-set the rate if that run lands far from 99.4%.
