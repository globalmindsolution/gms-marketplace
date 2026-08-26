# 0081 — create-prd's Plan-conformance dimension gains independent three-family corroboration; ADR-0004 amended

**Status**: Accepted · **Date**: 2026-08-25

## Context

`/acs:create-prd`'s dimension 7 "Plan conformance" is nominally the same
check name MAR-303/ADR-0080 hardened for the other four bootstrap-doc
skills (`/acs:create-quality`, `/acs:create-standards`,
`/acs:create-operations`, `/acs:create-principles`), but it was
deliberately left untouched by that ticket: create-prd's ground-truth shape
is genuinely different — it has no `Upstream inventory` section to
corroborate, and instead makes three independent kinds of claim a verifier
today only diffs against the executor's own output, never against an
outside ground truth: (a) every user answer recorded in
`clarifications.json` is claimed to be reflected in `prd.md`/`roadmap.md`;
(b) a brownfield plan's `Code evidence` citations are claimed to resolve
against the actual repo; (c) the plan's roadmap outline is claimed to match
the shipped `roadmap.md`. ADR-0004 warns that "a verifier judging against
the same-iteration plan certifies plan-conformant-but-wrong work" — today
dimension 7 has no independent floor for any of the three claim kinds
above, so a planner that drops an answer, mis-cites or fabricates a
brownfield code citation, or diverges the roadmap outline from what was
approved currently passes dimension 7 anyway. This ticket narrows that
tension the same way ADR-0080 narrowed it for its own dimension: by
re-anchoring the plan's claims onto the ledger, the repo, and the shipped
roadmap — never onto the plan's own prose. Since MAR-74 (ADR-0073),
ADR-0004 is append-only — amendments happen via new ADR files, never
in-place edits.

## Decision

**(a) D1-A — Single-script topology.** One new deterministic,
stdlib-only script, `prd_conformance_check.py`, with three rule families
(code-evidence, answer-fidelity, roadmap-outline), mirroring
`structure_lint.py`/`citation_check.py`'s CLI contract (stderr
`source:line: [rule] message` per finding, exit 0 clean / 1 on any finding
/ 2 on usage error), paired with a mandatory verifier semantic ceiling.
Chosen over three single-purpose scripts (3x the subprocess, CLI-contract,
and doc-set surface for one dimension of one verifier), prose-only
tightening (unpinnable by AC-3's "both pass and fail cases" — the same
argument ADR-0080 made for its own dimension), and direct
`citation_check.py` invocation (forecloses on two independent grounds: it
would need new flags — a `--heading` override and an empty-population
policy override — exactly the "extend `citation_check.py`'s grammar to
create-prd" this ticket rules out; and it writes the literal string
`citation_check.py` into `create-prd-verifier.md`, breaking
`tests/acs/test_citation_corroboration_verifiers.py:521-523`).

**(b) D2-a — Brownfield code-citation machinery imports, never
mirrors, `citation_check.py`.** `check_code_evidence` calls
`extract_citations(text, heading="Code evidence")` and
`resolve_and_check(citations, {"repo": repo_root}, plan_path)` unchanged;
zero bytes of `citation_check.py` are modified. Chosen over
re-implementing the ~60 lines standalone: `citation_check.py`'s
path-containment and symlink-`realpath` code has already needed two
post-merge security fixes, and importing inherits both fixes plus their
existing test coverage for free, at the cost of a coupling this decision
names explicitly rather than leaves implicit.

**(c) D3.1/D3.2-a — User-answer fidelity ground truth and pass bar.**
Ground truth is `clarifications.json` (via the same ledger every answered/
assumed entry already lives in), never the plan's own transcription of it
— re-deriving the population from the plan would let a planner grade its
own copy, the exact uncorroborated-trust gap this ticket closes. The pass
bar is reflection anchors (Option a, chosen): the plan records, per
`answered`/`assumed` ledger entry, one line naming the `C-<n>` id, the
target file (`prd.md` or `roadmap.md`), and a verbatim anchor string that
must occur in that file — emitting `answer-not-dispositioned` (a ledger
entry with no plan line — AC-3's "dropped user answer"),
`answer-anchor-not-found` (anchor absent from the named file,
whitespace-normalized), and `answer-anchor-file-unknown` (target not one of
the two produced files); an answer yielding no verbatim text records
`C-<n> N/A: <why>`, and every N/A is emitted on the manifest so the
verifier's ceiling must judge it, never silently accept it. Chosen over a
coverage-only pass bar (dispositioned-only, no anchor check — leaves the
"reflected in prd.md/roadmap.md" half of AC-2 prose-only) and over
cross-checking the executor's self-reported `clarifications_used` field
(trusting the executor's own report is the identical gap this ticket exists
to close).

**(d) D4-b+ii — Roadmap-outline consistency is a script rule family,
bidirectional and mode-scoped.** The plan declares milestones in a
one-line grammar carrying a verbatim heading excerpt; the script asserts
each declared heading occurs verbatim (whitespace-normalized) as a heading
in `roadmap.md` (forward direction, every mode) and, in the reverse
direction, that every `roadmap.md` heading was plan-declared — checked
against the full roadmap in greenfield/brownfield and scoped to only the
`--added-heading` values (derived from `git diff -- <prd_path>`, already
dimension 8's mechanism) in amend mode. Chosen over reusing
`structure_lint.py --sections` (evidence-blocked outright: this repo's own
`roadmap.md:273` milestone title contains a `;`, and `--sections` splits on
`;`, so a real milestone would be split into phantom required sections and
false-block) and over a one-way-only check (misses an executor-invented,
never-approved milestone — the sharper half of AC-3's "roadmap outline
diverges").

**(e) D5-fold — Folds into the existing dimension 7 "Plan conformance,"
no new dimension.** AC-2 names dimension 7 by number directly; appending a
new dimension would also have to land after the trailing `structure`/
`audience-style` pair (dimensions 10-11) to keep
`tests/acs/test_structure_audience_verifiers.py:293-316`'s ordering pin
green, breaking the established convention that those two stay the trailing
pair in every producer verifier. Dimension 7 keeps its name, number, and
position; the other ten dimensions are unchanged in substance.

**(f) D6 — Always blocking; mode-conditional only for the code-evidence
family.** No `severity="info"` degradation — `create-prd-verifier.md`
already states all findings are blocking except the waived `audience-style`
dimension, and the MAR-302-style carve-out is unavailable for the same
structural reason ADR-0080 recorded: the planner is re-spawned every
iteration, so every finding here is fixable in-run. The code-evidence
family alone is N/A in greenfield (no code to cite) — never a block — and
the empty-population policy is the caller's own (`code-evidence-empty`,
brownfield/amend only), never `citation_check.py`'s hard-coded
`citation-inventory-empty`, which would otherwise false-block every
greenfield run.

**(g) D7 — Planner-contract change, named explicitly.**
`create-prd-planner.md`'s required-heading list gains three sections
(`## Code evidence`, `## Answer fidelity`, `## Roadmap milestones`) and
their one-line grammars — a real contract change to a second agent
charter, named here rather than smuggled into a verifier-only edit, the
same posture ADR-0080 took for its own planner-contract change.

**(h) D8 — `clarifications.json` and the repo root declared as
verify-task inputs.** Although the verifier could already reach
`clarifications.json` by deriving the partition from `ticket.json`, and
runs with the repo as cwd, this decision declares both explicitly in
`<inputs>`/`<constraints>` anyway — an undeclared input is one a future
edit can silently drop, and the charter's own rule is "read every input —
you share no memory with anyone."

**(i) D9 — Iteration semantics; loop topology unchanged.** The mechanism
reads `iter-<n>-plan.md` for the **current** iteration and re-runs every
iteration. This ticket's AC-4 forbids loop-topology changes, and
create-prd's planner genuinely is re-spawned every iteration, so freezing
to `iter-1-plan.md` would itself be a topology change in disguise.

## Consequences

- ADR-0004 itself is never edited — this ADR amends it via the append-only
  ADR convention (`docs/adr/README.md`: "New ADRs are appended by the
  pipeline with the next sequence number").
- `create-prd-planner.md`'s required-heading list gains three sections and
  their grammars — a real behavioral contract change: a plan authored
  under the old (three-sections-absent) contract no longer satisfies the
  new floor, though it self-heals on the very next iteration's planner
  re-spawn (D9) since no mid-flight transition handling is needed.
- Every uncorroborated finding across all three families, and a script
  exit 2, are always `severity="blocking"` `Plan conformance` findings —
  except the code-evidence family, which is N/A (never a block) in
  greenfield.
- Dimension 7 keeps its name, number, and position; the verifier's 11
  numbered dimensions and their order are unchanged; no new dimension is
  added.
- `clarifications.json` and the repo root are newly declared verify-task
  `<inputs>`/`<constraints>` on `create-prd-verifier.md` and the mirroring
  sentence in `create-prd/SKILL.md`.
- `citation_check.py`, its test harness, `structure_lint.py`, MAR-303's
  mechanism for the other 4 bootstrap-doc skills, and loop topology
  anywhere are unchanged by this ticket.
- No settings key, schema, state-file shape, or artifact-path change
  (zero-migration): `prd_conformance_check.py` writes nothing;
  `severity="blocking"` and the `Plan conformance` dimension name both
  already exist.
