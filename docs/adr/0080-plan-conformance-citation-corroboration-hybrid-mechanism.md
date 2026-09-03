# 0080 — Plan-conformance verifier dimension gains independent citation corroboration; ADR-0004 amended

**Status**: Accepted · **Date**: 2026-08-25

## Context

Four bootstrap-doc skills — `/acs:create-quality`, `/acs:create-standards`,
`/acs:create-operations`, `/acs:create-principles` — share a byte-identical
`plan-conformance` verifier dimension (dimension 4): it diffs the executor's
output against the plan artifact but never independently re-checks the
planner's cited upstream facts (from `prd.md` NFRs, `architecture/`, and for
`create-standards` also `principles/`) against the actual source documents
the planner claims to have derived them from. A planner that mis-cites or
fabricates an upstream fact in `iter-<n>-plan.md`'s `Upstream inventory`
section currently passes `plan-conformance` anyway — the same class of
uncorroborated-trust gap MAR-302 fixed for `/acs:standardize-project`'s
additive-surface allowlist (ADR-0079), but for a different dimension and a
different loop shape: unlike `/acs:standardize-project`'s frozen
iteration-1 plan, these 4 skills' planners are genuinely re-spawned every
iteration, and loop topology is explicitly out of scope for this ticket
(AC-5). Since MAR-74 (ADR-0073), ADR-0004 is append-only — amendments happen
via new ADR files, never in-place edits.

## Decision

**(a) D1-C — Hybrid corroboration mechanism.** A new deterministic,
stdlib-only script, `citation_check.py`, mirrors `structure_lint.py`'s CLI
contract (stderr `source:line: [rule] message` per finding, exit 0 clean /
1 on any finding / 2 on usage error) and performs the mechanical floor: it
resolves every citation in the plan's `Upstream inventory` section against
the declared upstream roots (path containment) and asserts the cited
excerpt is present in the cited file (whitespace-normalized substring
match), emitting a resolved-citations manifest (`{claim, path, line,
excerpt}`) on stdout. The verifier's `plan-conformance` dimension runs this
floor and additionally re-opens every citation the script **resolves** and
judges substantiation itself — the semantic ceiling the mechanical floor
alone cannot provide. Chosen over a deterministic-only floor (blind to a
citation that resolves but does not substantiate its claim), a prose-only
semantic check (unpinnable by a behavioral test, and repeats the
LLM-auditing-LLM pattern ADR-0076 D-1 rejects), and an evidence-sidecar
reuse (the sidecar convention is scoped to produced doc files, not workspace
phase artifacts, and would duplicate the plan's own `Upstream inventory`
section).

**(b) D2-c — Mandatory verbatim quoted excerpt per citation.** The 4
planner charters' `Upstream inventory` citation grammar becomes the
one-line shape

```
- <claim> — `<path>[:line]` — "<verbatim excerpt>"
```

The path is
backtick-quoted, the optional `:line`/`:line-start-line-end` suffix is
advisory only (never a locus the script trusts), and the excerpt is now
**mandatory and verbatim** — a real planner-contract change to all 4
planner charters, not a verifier-only addition. The script's match rule
is whitespace-normalized substring containment (collapse runs of whitespace
to one space, strip ends). Chosen over existence-only or locus-presence
checks, both of which still let a mis-cited (not merely fabricated-path)
claim through — precisely the "mis-cited" half of this ticket's AC-3.

**(c) D3-a — Always blocking, no severity-degradation carve-out.** Every
uncorroborated citation (unresolved path, excerpt not found, or
resolved-but-non-substantiating) and a script exit 2 are always
`severity="blocking"` `plan-conformance` findings. Unlike MAR-302's
narrow, class-scoped `severity="info"` carve-out (ADR-0079), no degradation
applies here: MAR-302's carve-out was safe only because its allowlist was
**frozen** at iteration 1, with no next planner spawn in the same run to fix
a finding against it. Here the planner **is** re-spawned every iteration in
all 4 skills (loop topology unchanged, D6) — a citation-formatting or
mis-citation finding is cheap to fix in-run: the very next plan iteration
re-derives the `Upstream inventory` under the corrected contract. ADR-0063
stands as the cautionary precedent this decision does not repeat: it
*reversed* ADR-0057's carve-out because "a surfaced-but-ignorable finding
does not enforce" — choosing a carve-out here would invent a second
ignorable-finding exception with a strictly weaker structural excuse than
the one ADR-0063 already found unacceptable once.

**(d) D4-fold — Folded into existing dimension 4, no 9th dimension.** The
corroboration check is folded into the existing `plan-conformance`
dimension rather than appended as a new numbered dimension. This ticket's
AC-2 names "the verifier **plan-conformance** dimension" directly, and
folding keeps the "one of the **eight** names above" verifier output
contract, and its existing test pins, unchanged. Dimension 4 keeps its
name, number, and position; the other 7 check dimensions are unchanged in
substance.

**(e) D5-section-scoped — Extraction scoped to `Upstream inventory` only.**
The script parses only the plan's mandated `Upstream inventory` section —
mechanically decidable and exactly what "upstream-fact citation" means in
this ticket — never a whole-file scan (which would sweep in citations to
the target doc set, templates, or the plan's own self-references, producing
noise unrelated to upstream-fact corroboration).

**(f) D6 — Iteration semantics, loop topology unchanged.** The mechanism
reads `iter-<n>-plan.md` for the **current** iteration and re-runs **every**
iteration — unlike MAR-302's frozen `iter-1-plan.md`. This ticket's scope
explicitly forbids touching loop topology (AC-5); in these 4 skills the
planner genuinely is re-spawned per iteration, so `iter-<n>-plan.md` is a
different file each iteration, and freezing to `iter-1-plan.md` would
itself be a loop-topology change in disguise. This is also why (c)'s
always-blocking rule is safe here in a way MAR-302's carve-out was not.

**(g) D7-declare-prd-root — `prd_path` becomes a declared verify-task
constraint.** `prd_path` is declared today in all 4 sibling *planner*
charters but in none of the four *verifier* charters' `<constraints>`
enumeration, even though `architecture_path` (all four) and
`principles_path` (`create-standards`) already are. Since the mechanism's
roots must cover every upstream doc the planner may cite — including PRD
NFRs — `prd_path` is added as a newly declared constraint on all four
verifiers' input contract and on the four coordinators' verify-task
`<constraints>` sentence, satisfying AC-2's citation coverage in full,
user-ratified (C-7) over the alternative of freezing the verify-task
contract and carving PRD citations out of the mechanism.

## Consequences

- ADR-0004 itself is never edited — this ADR amends it via the append-only
  ADR convention (`docs/adr/README.md`: "New ADRs are appended by the
  pipeline with the next sequence number").
- The 4 planner charters' `Upstream inventory` citation grammar is a real
  behavioral contract change: a plan authored under the old (excerpt-
  optional) grammar no longer satisfies the new mandatory-excerpt floor.
- Every uncorroborated citation and a script exit 2 always block
  `plan-conformance` — there is no `severity="info"` escape hatch for this
  ticket's finding classes, unlike MAR-302's frozen-allowlist carve-out.
- The verifier output contract's "one of the eight names" enumeration is
  unchanged; no schema change, no new dimension name.
- Loop topology (per-iteration planner re-spawn) for all 4 skills, and
  `/acs:create-prd`'s own plan-conformance-adjacent verifier check, are
  unchanged by this ticket.
- `prd_path` is newly a declared constraint on the 4 verify tasks and their
  coordinators' verify-task constraints sentence.
- No settings key, schema, state-file shape, or artifact-path change
  (zero-migration): `severity="blocking"` and the `plan-conformance`
  dimension name both already exist; the plan artifact keeps its
  `iter-<n>-plan.md` name and per-iteration re-spawn.
