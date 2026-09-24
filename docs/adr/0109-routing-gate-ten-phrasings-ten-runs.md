# 0109 — The routing gate runs ten phrasings ten times, at 9/10 per skill and 1.0 for the suite

**Status**: Accepted · **Date**: 2026-09-24

**Amends**: [0107](0107-routing-gated-by-skill-not-by-prompt.md) (the phrasing
count and the two provisional rates). Everything else in 0107 — one-turn runs,
judging by skill rather than by prompt, must-pass negatives and controls,
`explicit` not gated, fail-closed on an unreadable result — stands.

## Context

ADR-0107 set three phrasings per described skill, three runs per case, and
provisional rates of 2/3 per skill and 9/10 for the suite, to be re-set from
data. The first attempt at a gate run was stopped after 208 runs ($15.63,
about $0.075 a run). Even that partial sample showed skills routing far below
any sensible floor — `review-code` 0/9, `docs-sync` 1/9, `create-api-contract`
3/9, `code` 4/9 — while every negative and control run passed.

Nine runs per skill cannot tell a 70% skill from a 90% one, and a 2/3 floor
lets a skill that misroutes one request in three ship. The owner set the bar
instead of waiting for a baseline to set it.

## Decision

- **Ten phrasings per described skill.** Each of the 24 skills a user reaches
  by description has ten `description` cases, at least one of them
  `confusable`. `tests/evals/check_cases.py` pins `MIN_PHRASINGS = 10`.
- **Ten runs per case.** The paid step passes `--runs 10`, with `-j 8` so a
  run of about 2,500 sessions finishes inside the gate's six-hour freshness
  window.
- **Each skill's pooled runs must route at least 9/10** (`--min-skill-rate 9/10`).
- **The suite must route every run** (`--min-suite-rate 1`).
- **The cost ceiling rises from $40 to $250.**

## Consequences

**The suite rate of 1.0 is the binding rule.** A suite that routes every run
has every skill at 100%, so the 9/10 per-skill floor never decides a verdict
while the suite rate is 1. It stays stated so that relaxing the suite rate
later does not silently drop the per-skill floor, and so a failing report
still names the weakest skills.

**One misroute in about 2,400 description runs fails the release.** That is
deliberate: the owner's position is that a request a user states plainly must
reach its skill every time. It also means the gate will fail until the weak
descriptions above are fixed — adding phrasings measures a description more
precisely, it does not improve it.

**A gate run costs about $190** (roughly 250 gated cases × 10 runs × $0.075)
and must be run from a host where `claude plugin eval` can open eight sessions
at once.

**Pre-push checks are unchanged.** `scripts/eval_changed.py` still runs a
touched skill's cases three times at 2/3; it is a fast local signal, not the
gate.
