# 0110 — Routing is graded on the first Skill call, not the first move

**Status**: Accepted · **Date**: 2026-09-27

**Amends**: [0107](0107-routing-gated-by-skill-not-by-prompt.md) (the one-turn
limit and the `tool_used` routing grader). Judging by skill rather than by
prompt, must-pass negatives and controls, and the rates set by
[0109](0109-routing-gate-ten-phrasings-ten-runs.md) all stand.

## Context

ADR-0107 made every routing run one turn, because the `tool_used` grader
counted Skill calls anywhere in the run and skills call skills: with ten
turns, a request misrouted to `/acs:ship` passed a step's case once `ship`
reached that step, and a request correctly routed to `/acs:code` failed a
leg's negative once `code` dispatched the leg.

One turn fixed that but graded the model's first MOVE, not its route. Tuning
the descriptions in September 2026 took the suite from about 80% to 99.4% of
description runs, and traced the remaining misses: nearly all were the model
globbing for the ticket or run files, or looking for a shell, before calling
the right skill. A real session routes on its next turn. With ADR-0109's suite
rate of 1.0 over about 2,400 runs, a 0.6% miss rate fails every release, and
further description wording did not move it.

## Decision

- **A routing run has three turns** (`max_turns: 3`, `ROUTING_TURNS` in
  `tests/evals/eval_cases.py`).
- **A positive case passes when the run's FIRST Skill call names its skill.**
  The grader is a `regex` over `target: trace` whose tempered token cannot step
  past an earlier Skill call:
  `^(?:(?!"name":"Skill","input":)[\s\S])*"name":"Skill","input":\{"skill":"(?:[\w-]+:)?<skill>"`.
  Later Skill calls — a skill invoking its steps or legs — cannot pass or fail
  a case, which is what the one-turn limit was for.
- **A leg's negative** is the same pattern with `match: not_contains`: the leg
  must not be the first Skill call.
- **A control** keeps `tool_used: Skill` at `0..0` with no `input_match`: any
  Skill call in the run is over-triggering.
- `tests/evals/check_cases.py` runs every pattern against traces shaped like
  the CLI's: own skill first (pass), own skill after another skill (fail), a
  neighbour such as `code-small` for `code` (fail), no Skill call (fail).

## Consequences

**A look before routing is no longer a miss; a wrong first route still is.**
What the gate now fails on is a request whose first Skill call is another
skill — an acs neighbour, or a built-in such as `code-review` — or a run that
never routes within three turns.

**A run costs about $0.09 instead of $0.075**, so a full gate run is about $230
and the ceiling rises from $250 to $300.

**The grader depends on the trace's compact JSON shape**
(`"name":"Skill","input":{`), read from CLI 2.1.281. A CLI that changes it
makes every positive case fail rather than pass, which the gate reports as a
routing collapse — loud, not silent.

**Every routing number before this ADR is on the one-turn grader** and is not
comparable with numbers after it.
