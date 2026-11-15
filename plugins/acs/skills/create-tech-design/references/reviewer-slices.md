# The review — three slices of one reviewer

Read before every review.

The reviewer has nine check dimensions, so the review is sliced by
dimension: three fresh instances of the SAME
`acs:create-tech-design-reviewer` agent spawned in ONE message, each task
carrying `slice="<id>"` and `<constraint name="dimensions">` with its
dimension numbers:

| Slice | Dimensions (numbers as in the reviewer agent) |
|-------|-----------------------------------------------|
| `decision` | 1 alternatives · 3 feasibility · 4 nfr (with its `standards` sub-check) |
| `conformance` | 2 consistency (with its `standards` sub-check) · 8 authoring-conformance · 9 lld-consistency |
| `form` | 5 completeness — the ONLY slice that runs `mermaid_lint.py` and `acs.py design check` on the draft · 6 structure — the ONLY slice that runs `structure_lint.py` · 7 audience-style |

Grounding policing applies in every slice. Each slice writes
`iter-<n>/reviewer-<id>.md`; join them with `acs.py notes merge --out
iter-<n>/reviewer.md iter-<n>/reviewer-decision.md
iter-<n>/reviewer-conformance.md iter-<n>/reviewer-form.md`.
The slices own disjoint dimensions, so the join is the synthesis, plus one
**de-duplication** step: drop a finding that cites the same location and
the same defect as another slice's finding (a stale snapshot both
`consistency` and `lld-consistency` saw, say), keeping the higher severity,
and say so in the joined report — append a `## De-duplicated findings`
section naming each dropped finding and the one it duplicates (re-apply it
whenever the join is redone). The de-duplicated findings are the ones the
pass rule and the next designer see.

Spawn fresh — it sees artifacts (the draft, the requirements, the HLD, the
feature's LLD documents, the code), never the designer's reasoning. Each
check is a finding `dimension`:

- `alternatives` — >=2 options genuinely weighed with real trade-offs, not strawmen;
- `consistency` — the design agrees with the actual codebase and the HLD;
  `## HLD views affected` is accurate and complete (no undeclared view
  change, no declared change that is not needed); also runs a
  `standards` sub-check against the standards set at `standards_dir` when set,
  emitting `dimension="standards"` findings for design decisions this
  tech-design.md introduces (changeset-scoped block/surface, graceful
  degradation when unset);
- `feasibility` — implementable with the documented tech stack and constraints;
- `nfr` — security and performance (and other applicable NFRs) concretely
  addressed, not hand-waved; the same `standards` sub-check also applies to
  NFR-shaped `standards/` content (testing-conventions, review-checklist
  performance/security/operability criteria);
- `completeness` — all six required sections present and substantive, the
  four LLD subsections present, every "n/a" carrying a reason; the one-line
  decision first; the version front matter valid; Mermaid lint clean;
- `structure` — `structure_lint.py` over the template-derived sections;
- `audience-style` — the hand-off reads for reviewers weighing a decision;
- `authoring-conformance` — the draft matches its authoring notes;
- `lld-consistency` — cross-category agreement across the snapshots and the
  documents they link (a flow message names an operation the api document
  has; an entity a flow or an operation carries is one the data document
  has), and snapshot freshness (every linked version is the document's
  current version).

**Pass rule.** The iteration passes only if EVERY reviewer slice returned
`status="completed"` with zero blocking findings; any slice's blocking finding
blocks, and ALL slices' findings go verbatim to the next designer. A slice
that failed or returned no usable result fails the iteration: never "pass
with a missing slice".
