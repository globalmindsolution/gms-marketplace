# 0083 — Bootstrap-doc skills' remediation loops become execute → verify only; ADR-0004 amended, ADR-0080/ADR-0081 loop-topology statements superseded

**Status**: Accepted · **Date**: 2026-08-26

## Context

MAR-305 drops the per-iteration planner re-spawn across the 5 bootstrap-doc
skills — `/acs:create-prd`, `/acs:create-quality`, `/acs:create-standards`,
`/acs:create-operations`, `/acs:create-principles` — the same decision class
ADR-0004's `except /acs:code` carve-out already records for `/acs:code`
(MAR-70/71/72) and that ADR-0077/0078/0079 each extended to
`/acs:docs-sync`/`/acs:create-project`/`/acs:standardize-project`
respectively: the plan is authored once, before the loop, and iteration-2+
findings are remediated without a new plan. Each of these 5 skills' verifiers
already independently re-derives its own ground truth — `citation_check.py`
for the 4 create-quality/-standards/-operations/-principles siblings
(ADR-0080), `prd_conformance_check.py` for `create-prd` (ADR-0081) — so the
per-iteration re-plan the pre-MAR-305 topology spawned on iteration 2/3 was
pure overhead: a mechanical restatement of findings the executor can receive
directly, exactly as ADR-0077/78/79 found for their own skills.

ADR-0080's decision (c)/(f) and Consequences, and ADR-0081's decision (i) and
Consequences, each explicitly declared loop topology **unchanged** for these
5 skills — a correct, correctly-scoped statement about those two tickets'
own non-goals (MAR-303/MAR-304 both explicitly excluded loop-topology changes
from scope). MAR-305 now makes that later change, so those specific
loop-topology statements are superseded here — never rewritten in place, per
this repo's append-only ADR convention (`docs/adr/README.md`: "New ADRs are
appended by the pipeline with the next sequence number"). The two ADRs'
corroboration-**mechanism** statements are untouched: `citation_check.py`,
`prd_conformance_check.py`, their test harnesses, and both verifiers'
independent-substantiation behavior are unaffected by this ticket (confirmed
via `git diff --name-only origin/main...HEAD | grep -E
"citation_check\.py|prd_conformance_check\.py|create-.*-verifier\.md"` →
no match).

## Decision

**(a) Execute → verify only, for all 5 skills.** Each of `/acs:create-prd`,
`/acs:create-quality`, `/acs:create-standards`, `/acs:create-operations`, and
`/acs:create-principles`'s remediation loop is now **execute → verify only**:
the plan is authored exactly once per run, before the loop starts, and
iteration-2+ findings from the verifier route directly to the **executor**'s
`<task>` `<context>` — not to a new plan. This amends ADR-0004's
`except /acs:code` remediation-loop carve-out to also name all 5
bootstrap-doc skills, mirroring ADR-0077/0078/0079's own stated scope
("amending ADR-0004's `/acs:code` carve-out to also name `/acs:docs-sync`" —
`docs/adr/README.md` lines 69-71) extended here to one ADR covering 5 skills
in one ticket, the same one-ADR-per-ticket unit ADR-0080 already established
for MAR-303's 4 skills.

**(b) Supersedes ADR-0080's decision (c), decision (f), and Consequences
loop-topology statements.** ADR-0080 decision (c) ("the planner **is**
re-spawned every iteration in all 4 skills (loop topology unchanged, D6)"),
decision (f) ("**D6 — Iteration semantics, loop topology unchanged**… This
ticket's scope explicitly forbids touching loop topology"), and the
Consequences bullet ("Loop topology (per-iteration planner re-spawn) for all
4 skills… unchanged by this ticket") were true and correctly scoped **as
decisions about MAR-303** — that ticket correctly declined to touch loop
topology. MAR-305 later changes it. ADR-0080 itself is not edited; these
three loop-topology statements are superseded by decision (a) above for
`/acs:create-quality`, `/acs:create-standards`, `/acs:create-operations`, and
`/acs:create-principles`. ADR-0080's corroboration-mechanism decisions
((a), (b), (d), (e), (g)) and Consequences bullets about `citation_check.py`,
the mandatory-excerpt grammar, the always-blocking posture, and the
dimension-4 fold are **not** superseded — they remain correct and unchanged.

**(c) Supersedes ADR-0081's decision (i) and Consequences loop-topology
statement.** ADR-0081 decision (i) ("**D9 — Iteration semantics; loop
topology unchanged**… create-prd's planner genuinely is re-spawned every
iteration") and the Consequences bullet ("…and loop topology anywhere are
unchanged by this ticket") were true and correctly scoped **as a decision
about MAR-304** — that ticket correctly declined to touch loop topology.
MAR-305 later changes it. ADR-0081 itself is not edited; this loop-topology
statement is superseded by decision (a) above for `/acs:create-prd`.
ADR-0081's corroboration-mechanism decisions (the three-family
`prd_conformance_check.py` topology, the answer-fidelity/roadmap-outline
rules, the always-blocking posture) and Consequences bullets about them are
**not** superseded — they remain correct and unchanged.

**(d) Not touched by this amendment.** Two clauses stay exactly as
ADR-0077/78/79 already established them, unchanged by this ticket:

- **The artifact-naming clause stays `/acs:code`-only.** None of the 5
  skills renames its plan artifact to `plan.md`; each keeps
  `phases/<skill>/iter-<n>-plan.md` (`n` always 1, written once, never
  rewritten on a later iteration).
- **ADR-0004's actual subject — verifier independence — is unchanged.** All
  5 verifiers' independent-corroboration mechanisms (`citation_check.py` for
  4 of them, `prd_conformance_check.py` for `create-prd`) continue to
  re-derive their ground truth from outside the plan rather than anchoring
  on the planner's output.

## Consequences

- ADR-0004 itself is never edited — this ADR amends it via the append-only
  ADR convention (`docs/adr/README.md`: "New ADRs are appended by the
  pipeline with the next sequence number").
- ADR-0080 and ADR-0081 are likewise never edited — their loop-topology
  statements named in decisions (b)/(c) above are superseded by this ADR;
  their corroboration-mechanism statements stand, unchanged and
  uncontradicted.
- A run of any of the 5 bootstrap-doc skills that needs 3 iterations spawns
  exactly one planner subagent across the whole run; the iteration cap (max
  3) and the fixed (non-lane-conditional) verify depth are unchanged.
- Each of the 5 skills' planner charters narrows accordingly: none carries a
  "route iteration >= 2 findings back into a new plan" responsibility any
  longer — that responsibility moves to the executor's `<context>` handling,
  mirroring `/acs:code`'s MAR-71 shape and ADR-0077/78/79's own skills.
- `citation_check.py`, `prd_conformance_check.py`, their test harnesses, and
  all 5 verifiers' independent-corroboration behavior are unchanged by this
  ticket.
- No settings key, schema, state-file shape, or artifact-path change
  (zero-migration): each skill keeps its `iter-<n>-plan.md` name and its
  existing dimension names/numbers/order.
