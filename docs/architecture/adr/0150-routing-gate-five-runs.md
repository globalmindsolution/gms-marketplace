# 0150 — The routing gate runs each case five times

**Status**: Accepted · **Date**: 2026-11-20

**Amends**: [0111](0111-routing-gate-ten-phrasings-ten-runs.md) (the run count
only). Ten phrasings per described skill, the 9/10 per-skill floor, the
$250 ceiling and, from [0112](0112-routing-suite-rate-99-percent.md), the
99/100 suite rate all stand.

## Context

ADR-0111 set `--runs 10`, which with about 290 gated cases is roughly 2,900
sessions per gate run. The v0.7.1 cut ran it on a subscription: after about
1,670 sessions the account hit its five-hour usage limit, and the remaining
1,232 sessions each failed with the limit message instead of routing. The run
spent $125.77 and produced no verdict — `eval_gate.py` correctly read the
failed sessions as misses, so the aggregate (0.575) measured the quota, not the
descriptions.

A gate that cannot finish inside one usage window on the host it is run from
cannot release anything. Waiting out the window and re-running does not help:
the next run hits the same wall at the same point.

## Decision

- **Five runs per case.** The paid step passes `--runs 5`, still with `-j 8`.
  A gate run is about 1,450 sessions, roughly $110 at ADR-0111's $0.075 a run,
  and fits inside one usage window with headroom.
- **The thresholds do not change.** `eval_gate.py`'s rates are ratios over
  pooled runs, so `--min-skill-rate 9/10` and `--min-suite-rate 99/100` keep
  their meaning; only the sample behind them shrinks.

## Consequences

**Each skill is judged on 50 pooled runs, not 100.** Ten phrasings × five
runs. The 9/10 floor allows five misses per skill instead of ten; a skill at
the floor's edge is resolved less precisely, but every phrasing is still run
more than once, which is what ADR-0107's move from per-prompt to per-skill
grading needed.

**The suite allows about 12 misses in 1,200 description runs.** At ADR-0112's
measured 0.6% first-move miss rate that is about 7 expected misses — the same
margin in proportion as at ten runs, with a wider spread around it.

**A failed session is still a miss.** If a usage limit or an outage cuts a run
short again, the verdict will be red and must be read, not trusted: the
failures name the limit, not a skill.

**Pre-push checks are unchanged.** `scripts/eval_changed.py` still runs a
touched skill's cases three times at 2/3.
