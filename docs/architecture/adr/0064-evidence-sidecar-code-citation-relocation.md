# 0064 — Relocate code-evidence citations into per-doc `.evidence.md` sidecars

**Status**: Accepted · **Date**: 2026-07-19

## Context

G37's brownfield `/acs:create-requirements` producer and `create-architecture`
cite every extracted requirement/claim to a repo source `path:line` inline in
the human-facing `docs/requirements` / `docs/architecture` body (100%
code-cited coverage, C-22 DRAFT/human-confirm-required discipline). G38/G39's
readable-docs goal (PRD, MAR-149 epic design) treats those raw source anchors
as machine-facing clutter inside a document meant for human readers — the
same clutter G38's structure/audience-style gates already fight for prose
shape.

The design's scope rule bounds what moves: a repo source `path:line` anchor
(`.py`/`.json`/`.sh`/`.xsd`, plus `SKILL.md:line`) — never an inter-doc `.md`
link (`design.md:NN`, `contracts.md:NN`, `overview.md:NN`, `data-model.md:NN`,
`prd.md:NN`), never a bare filename without a line anchor, never a `.yml:line`
ref. Those forms are workspace provenance or plain doc-set navigation, not a
code-evidence citation, and stay in the body untouched.

## Decision

**Option B1 — per-doc parallel `.evidence.md` sidecar file.** Every code-cited
requirement/architecture doc gets a companion `<doc-basename-without-.md>.evidence.md`
file next to it. The human body keeps the clause plus a stable clause anchor
(the doc's existing row/section/heading identity is reused wherever one
exists; a new `{#id}` marker is added only where none does) and carries **no**
inline `path:line`; the sidecar maps `clause-anchor -> [path:line, ...]` in
human-auditable markdown. This is the epic design's recommended option,
confirmed by the coordinator before minting children.

Two refinements settled by the user's C-5 steer and carried into this
decision:

- **Human bodies show no sources/evidence to readers** — the sidecar is
  strictly machine-facing; a body may name the sidecar's existence in prose
  (e.g. "see the companion `<doc>.evidence.md` sidecar"), but never embeds a
  `path:line` token itself.
- **The producing verifier actively checks grounding**, not passive storage:
  body-grep-to-0 for the in-scope regex, a sidecar-exists check for any
  code-cited doc, an anchor-join confirming every body clause anchor has
  >= 1 sidecar entry, and an amend-mode count-not-reduced check (Spec 01,
  `create-requirements-verifier.md` dimension 6 / `create-architecture-verifier.md`
  dimension 3).

**Sidecar filename convention (C-4, settled during this ticket's `code`
phase).** The canonical rule strips the doc's `.md` extension:
`<doc-basename-without-.md>.evidence.md` — e.g.
`runtime-coupling-inventory.md` -> `runtime-coupling-inventory.evidence.md`,
`tabp-usage-read.md` -> `tabp-usage-read.evidence.md`, and
`docs/requirements/functional/tabp.md` -> `tabp.evidence.md` (not
`tabp.md.evidence.md`). The exclusion predicate used everywhere a doc-set is
enumerated (`is_evidence_sidecar`) only checks `endswith(".evidence.md")`, so
either form would have worked mechanically; the strip form is adopted as the
single deterministic rule for future consumer-repo producers.

**This repo's dogfood migration — ground-truth footprint (re-derived,
supersedes the design's estimate).** The design approximated "`~26` code
citations in `runtime-coupling-inventory.md` plus `~7` scattered
architecture `path:line` refs, `docs/requirements` citation-free"
(`design.md:504-508`). Re-running the scope-rule regex against the live tree
finds exactly **3 files / 18 in-scope citations**:

- `docs/architecture/lld/runtime-coupling-inventory.md` — 16 citations = 8
  distinct anchors, each cited twice (the "Runtime-coupled surfaces" table's
  "Verified entry points" column, and the "Entry-point anchor verification
  record" table's "Anchor" column). Both occurrences are preserved as
  distinct sidecar entries — never deduped to 8 — so the coverage-not-reduced
  gate holds at `>= 16`.
- `docs/architecture/lld/flows/tabp-usage-read.md` — 1 citation
  (`tabp_helper.py:1072-1077`). This is a frozen retired-product flow doc;
  it migrates the same way as any other code-cited doc (no carve-out), so
  the global body-grep-to-0 invariant stays free of a special case.
- `docs/requirements/functional/tabp.md` — 1 citation (`SKILL.md:173-177`).
  The design's Assumption 3 called `docs/requirements` "citation-free"; the
  full scope-rule regex (including its own `SKILL.md:line` branch) finds this
  one token, refining Assumption 3 to "near-citation-free, exactly one
  in-scope citation." It is migrated, not carved out, for the same
  deterministic-syntactic-gate reason as the flow doc above — a semantic
  "grounding vs. historical narration" distinction is not automatable.
- `docs/architecture/lld/contracts.md` has 0 in-scope citations both before
  and after (its only `path:line`-shaped ref, `ci.yml:197-199`, is an
  out-of-scope `.yml` extension) — no sidecar for it.

The new `tests/acs/test_evidence_sidecar_topology.py` coverage/topology test
(this child, MAR-152) is the objective, re-runnable proof that this
100%-code-cited coverage was **relocated, never reduced**, and that C-22
markers are unaffected.

## Alternatives considered

- **Option B2 — in-file appendix below a machine-readable marker.** No new
  files; single-file locality. Rejected: the marker becomes load-bearing for
  every doc-quality gate (audience-style, `structure_lint`, G29 line-length,
  `mermaid_lint`) — each must learn to split the file at the marker and judge
  only the human half — and keeps machine content inside the human file,
  which is exactly the clutter this goal fights, merely folded below a fold.
- **Option B3 — single central evidence index** (one `evidence-index.md` or
  `evidence.json` per doc tree). Simplest coverage assertion and smallest
  file-count delta. Rejected on operability: it destroys claim-to-evidence
  locality, and a single hot file becomes a cross-ticket merge-conflict
  magnet on every doc-touching PR in a marketplace repo where many tickets
  touch `docs/architecture`/`docs/requirements` concurrently.
- **Append-form sidecar filename** (`<doc-basename>.md.evidence.md`,
  keeping the `.md`). Rejected in favor of the strip form: 2 of this
  ticket's 3 dogfood sidecars and the exclusion-test fixtures already used
  the strip form, and a single canonical rule is required for the producer
  charters that future consumer-repo docs will follow.

## Consequences

- Every code-cited `docs/requirements`/`docs/architecture` doc in any
  G37-code-cited repo (C-20 consumer-general) now ships a companion
  `.evidence.md` sidecar alongside it; the human body is citation-free by
  construction and by a blocking verifier check, not merely by convention.
- This is an **intentional, non-byte-identical migration** — it rewrites the
  3 committed docs named above (strips their inline `:line` suffixes, adds 3
  new sidecar files). It carries no byte-identical guarantee of any kind;
  that property belongs to ADR 0065's template-config default (Decision C),
  a different, unrelated guarantee for a different mechanism.
- G37's 100%-code-cited coverage is preserved, not reduced: the coverage/
  topology test's pinned pre-migration constants (16 / 1 / 1, re-derived
  this task, not the design's "~26+~7") gate every future edit to these
  docs and sidecars.
- C-22 DRAFT/human-confirm-required markers are unaffected — this repo's
  `docs/requirements` set predates G37 and carries no such marker in any
  real area file today (including the migrated `functional/tabp.md`), so
  the migration neither removes nor introduces one; the topology test's
  check (c) is written as a general, re-runnable before/after invariant so
  it is meaningful for a consumer repo whose requirements DO carry markers.
- Doc-enumerating tests that walk `docs/**` (`test_mermaid_diagrams.py`) now
  skip `*.evidence.md` sidecars via the shared `tests/acs/evidence_sidecar.py`
  predicate (Spec 02) — a sidecar is machine-facing, not a "doc," and is
  exempt from the audience/structure/diagram-lint gates that apply to human
  bodies.
- The coverage/topology check lives under `tests/acs/`, not
  `plugins/acs/hooks/scripts/`, so the 49 hook-script count is unaffected;
  no new skill/agent/schema/settings key is introduced by this decision.
