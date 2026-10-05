# /acs:analyze-requirements — when the user is not reachable

Open this when this session cannot ask the user anything and no answers
were relayed — the definition is the first paragraph below. A run with a
reachable user reads none of it: every question goes in the one grouped ask.

**Where the cross-references below point.** "Where the analysis goes" is
SKILL.md's Stage 2 section.

The user is unreachable when this session cannot ask — AskUserQuestion is not
available or returns nothing (a non-interactive run: `claude -p`, an eval, a
scheduled run) — and no answers were relayed in a `/acs:ship` brief. Then, and
only then:

**A question with a conventional default is an assumption, not a blocker.**
When the requirements' words plus the repository's conventions settle a detail
well enough that a competent implementer would not stop to ask — "prints"
means stdout; a credential check is exact and case-sensitive unless the
requirements say otherwise; argument counts the requirements never mention
are out of scope; an unspecified error path follows the codebase's existing pattern —
record the default as an assumption (`--source assumption --rationale
"..."`), state it in the README's `## Questions and assumptions`, propose the
matching criterion rewrite in `## Refined acceptance criteria`, and keep
`ready_for_planning: true`. The
2026-09-15 release gate lost a two-line login ticket to exactly three such
defaults asked as blockers, on a run with nobody to answer them. When the user
IS reachable, the same defaults are asked — as confirmations, in the one
grouped ask — never silently assumed: an assumption is a finding for a human
to confirm, never a silent default.

Group (c) and (d) proposals stay open ledger entries and the requirements
and the ticket are left as they are — except a run's missing feature, which
is inferred, because nothing can be published without one: the best-matching
PRD feature slug, or a new slug from the requirements' subject when none
fits, recorded as an assumption (`--source assumption --rationale "..."`) and
then with `requirements refine` `{"feature": "<slug>"}`. A group-(a) question
with a fallback is recorded as an assumption on that fallback; one where every
default could build the wrong thing makes the work not plannable —
`record-clarify --blocking-open`, and
`references/not-ready-for-planning.md` carries what to do about it. The
document questions are never assumed into the settings: an open share choice
keeps the analysis local for this run only (Where the analysis goes, above).
