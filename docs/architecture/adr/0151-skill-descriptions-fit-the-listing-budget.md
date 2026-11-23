# 0151 — Skill descriptions fit Claude Code's skill-listing budget

**Status**: Accepted · **Date**: 2026-11-23

**Refines**: [0112](0112-routing-suite-rate-99-percent.md), whose tuned
descriptions keep their trigger clauses and their "Call it as your first
action" sentence. Everything else they said moves to the skill bodies.

## Context

The v0.7.1 routing gate (ADR-0150, five runs a case) failed. Most skills routed
every run, but three fell far below the 9/10 floor: setup 15/55, ship 41/50,
update 41/50. The suite routed 1,318 of 1,380 runs. Every miss had the same
shape: the session spent its one turn on something other than a Skill call.

The cause was not the descriptions' wording. Claude Code (2.1.330) lists every
skill to the model under a character budget: 30,000 characters in that build,
or the context window × 4 × 1% when no override applies. The listing holds
Claude Code's bundled skills, acs's skills and any other plugin's. When the full
listing is over budget, the CLI walks the skills in priority order, keeps each
description while it still fits, and lists the rest **by name only**. An
isolated session with only acs loaded was over budget (62 skills, 42,723
characters), and acs's own entries were about 24,400 characters. Asked to print
its listing, that session showed descriptions for the first 27 acs skills and
none for `set-doc-status`, `setup`, `ship` and `update`.

A skill listed by name only is routed on its name. `set-doc-status` and, in part,
`ship` survive that. "Add the CI gate that fails a PR below the coverage
target" and "which acs version am I running" do not lead to `setup` or `update`.

The descriptions had grown past the AUTHORING rule of "under ~2 lines" to
800–1,300 characters each, mostly mechanics: what a skill writes, how it
reviews, what it never does.

## Decision

- **Every description is its trigger clause.** It says what the skill does in
  one clause and when to use it in the words users say, and it keeps the
  "Call it as your first action" sentence ADR-0112 measured. Mechanics move to
  the body, which the model reads only once the skill is invoked. acs's listing
  goes from about 24,400 to about 16,100 characters. In the same isolated
  session, every acs skill then carries its description.
- **`when_to_use` is not used.** The CLI appends it to the description, so it
  spends the same budget. `docs-sync` and `release` drop theirs; the body
  already says it.
- **A unit test holds the budget.** `tests/acs/test_skill_listing_budget.py`
  renders acs's entries as the CLI does and fails a PR when they pass
  17,000 characters, or any one entry passes 900. It runs in CI, so an
  over-long description is caught for free rather than by a paid gate run.

## Consequences

**The budget is not acs's alone.** A consumer with more plugins installed has
less of it. The CLI also reorders by each skill's recent use, so which skills
lose their descriptions differs from one consumer to the next. Keeping acs's
share well under the total is the only lever a plugin has; `skillOverrides` and
`skillListingBudgetFraction` are the user's settings, not the plugin's.

**Routing was measured with the long descriptions.** The shorter ones keep every
trigger phrase that the description-pin tests name. Only the next gate run says
whether the 99/100 suite rate still holds, and it is the release gate.

**The 17,000 figure is a ceiling with room, not a target.** The figure leaves
room for a new skill. Growing past it means shortening, not raising it.
