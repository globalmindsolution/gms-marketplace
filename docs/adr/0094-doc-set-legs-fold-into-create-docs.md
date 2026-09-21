# 0094 — The four doc-set legs fold into `/acs:create-docs`: one skill, a declared table of sets, an executor and a verifier, no planner

**Status**: Accepted · **Date**: 2026-09-14

**Amends**: [0085](0085-doc-bootstrap-parallel-fan-out.md) (the fan-out
mechanics stand; the per-leg skills they fanned out to are gone),
[0091](0091-design-phase-entry-point-fold.md) (the doc-set legs were collapsed
after all; `/acs:project`'s entry-point fold stands).

## Context

ADR-0011 gave each product doc set its own skill; ADR-0085 put an umbrella,
`/acs:create-docs`, over two of them to run them in parallel; ADR-0091 widened
the umbrella to all four and made the legs internal, explicitly choosing an
**entry-point fold, not a collapse** — each leg kept its SKILL.md, its
planner/executor/verifier trio, its `pre-`/`post-` hook scripts, its gate
and its sentinel, and the umbrella dispatched each with a real
`Skill(acs:<leg>)` call. ADR-0092 then declared per-skill machinery and noted
that the four legs were "structurally near-identical (359–401 lines each) and
will hold eight agent files between them for work that differs only in which
directory it writes", deferring the collapse to "its own evidence rather than
momentum".

The evidence is a `diff`. `create-quality/SKILL.md` against each sibling:
133, 176 and 200 differing lines of roughly 380 — every one a substitution of
the set name, the settings key, the delivery-ticket title, the output files
with their required sections, the audience register, the upstream inputs, or
the template directory. The three agent files differed the same way (57–84
lines of 107–168). Nothing in the legs' *behaviour* differed: read the PRD
and the architecture set, decide bootstrap vs re-run, copy templates, tailor
them to the detected stack, record cited upstream facts, verify. Four skills,
twelve agent files and eight hook scripts were carrying one table.

Two further costs had accumulated on top. The umbrella described each leg's
loop by citation, a convention every leg edit could break; and the legs'
planners were the clearest case of ADR-0092's class-D finding — a planner
whose deliverable is a plan for copying a template is a second copy of the
copying.

## Decision

**`/acs:create-docs` absorbs the four legs.** It becomes a hooked product
skill in its own right — in `PRODUCT_SKILLS`, with `pre-`/`post-create-docs.py`
and one `GATES` row — and the four leg skills, their twelve agent files and
their eight hook scripts are deleted.

**What a set *is* lives in one table.** `acs_lib.DOC_SETS` declares, per set:
the settings key that locates it, the delivery-ticket title, the template
directory, the output files in order (the first is the sentinel that says the
set has shipped) with the sections each must carry, the audience register,
the upstream inputs (which PRD slice; the architecture set; whether the
principles set is read when present), and the dependency edges. The fan-out
views (`DOC_BOOTSTRAP_DEPENDENCIES`, `DOC_BOOTSTRAP_SETTINGS_KEY`,
`DOC_BOOTSTRAP_SENTINEL`, `DOC_BOOTSTRAP_FANOUT_V1`, `DOC_SET_TITLES`) are
derived from it and keyed by set name. The skill's Start snippet prints the
table; the coordinator composes task constraints from it and never restates
it; adding a fifth set is one row plus its templates.

**The run unit is `(create-docs, doc_set)`.** `skill-start.py --skill
create-docs --doc-set <set> --allocate` mints one delivery ticket per set,
titled from the table and carrying `doc_set` on the ticket (and its index
entry), so a resume (`/acs:create-docs <ticket-id>`) knows what it resumes
without parsing a title, and `fanout_batches` can tell an in-flight set by
field. Each set keeps its own partition, `create-docs-state.json`,
`pipeline-state.json` (`flow: "product"`, step `create-docs`), branch,
worktree and docs-only PR. Failure isolation and the no-batch-ledger rule
stand exactly as ADR-0085 decided them.

**Class D machinery: an executor and a verifier, no planner.** One
`create-docs-executor` authors any set — reads the declared upstream inputs,
decides the mode from the disk, runs the ADR-0012 consistency step,
bootstraps each file from its template and tailors it — and writes its
authoring notes, `iter-<n>-authoring.md`: mode with evidence, the Upstream
inventory in the MAR-303 citation grammar, consistency findings, decisions.
One `create-docs-verifier` judges the set fresh across the same eight
dimensions the leg verifiers had, with `plan-conformance` renamed
`authoring-conformance` and `citation_check.py` pointed at the notes. The set
reaches both agents as task constraints; the same two files serve all four.

**One gate, once.** Every set's only precondition is the architecture doc
set, so the pre-hook checks it once at the Skill call. ADR-0085's fail-fast
carve-out for the shared gate is gone because there is no longer a leg whose
own gate could fire after the umbrella started.

**The former leg names stay recognisable for one release.**
`parse_doc_set_arg` resolves `create-quality` to `quality`, exactly as `--for`
stays accepted, and a delivery ticket minted before `doc_set` existed is still
matched by its title.

## Consequences

- 32 skills → 28; 53 agent files → 43; 20 hooked skills → 17; 6 internal
  legs → 2 (`/acs:project`'s). The `internal` map and the entry-point fold
  pattern survive for the project legs, where the two legs genuinely differ.
- `phase_of("create-quality")` no longer resolves; `create-docs` is a
  design-phase skill directly. `/acs:metrics` shows one `create-docs` row per
  delivery ticket, the set visible on the ticket.
- The eval dataset loses the eight leg routing probes (explicit + negative
  per leg), the four leg skill-manifest cases and the twelve leg gate cases,
  and gains three `create-docs` gate cases; the routing baseline's scenario
  set moves to 1.7.0 and the surface fingerprint changes, so the next
  measurement is the new baseline.
- ADR-0011's one-skill-per-doc-set rule is superseded for these four sets:
  one skill per *kind of work* (bootstrap a templated doc set from declared
  upstream), with the set as data. ADR-0083's loop topology is moot for
  them (no plan phase at all). ADR-0085's umbrella mechanics stand; its
  "legs stay real, Skill-invocable skills" premise, and ADR-0091's "not a
  collapse" decision for these four, are reversed here — deliberately, on
  the evidence above, and only for the four whose difference was a table.
- Per-role `models.overrides.create-<set>` settings become unknown keys;
  `models.overrides.create-docs.{executor,verifier}` is the replacement.
- This is the first authoring skill through ADR-0092's planner removal; the
  eleven remaining class-D planners follow the same shape (authoring notes
  the verifier corroborates) one skill at a time.

## References

- **ADR-0011** — one skill per doc set (superseded for the four sets here).
- **ADR-0012** — the design-time doc-consistency step the executor now runs.
- **ADR-0080 / ADR-0081 / MAR-303** — citation corroboration; unchanged in
  mechanism, relocated from `iter-<n>-plan.md` to `iter-<n>-authoring.md`.
- **ADR-0085** — the fan-out mechanics this ADR keeps.
- **ADR-0091** — the entry-point fold; kept for `/acs:project`, reversed for
  the doc sets.
- **ADR-0092** — the four work classes; this is class D applied.

## Amendment — v0.5.0 (the implementation-pipeline redesign)

The fold stands in full: one hooked skill, the declared `DOC_SETS` table as the
single source, one executor plus one verifier for every set, no planner, and
one delivery ticket per set.

The allocating call is **`acs step start --step create-docs --doc-set <set>
--allocate`**. `skill-start.py` was removed in v0.5.0 and its flags moved onto
the `acs` CLI; the run unit `(create-docs, doc_set)` this ADR defined is
unchanged, and so is the rule that the allocating call runs in the session
checkout rather than a per-set worktree
([0085](0085-doc-bootstrap-parallel-fan-out.md) D3.2,
[0087](0087-ticket-id-allocation-fail-closed-reconciliation.md)).
