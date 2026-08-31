# 0085 — Doc-bootstrap parallel fan-out: new umbrella skill, phase-level interleave, worktree-per-leg delivery, declared dependency/eligibility, no new ledger, scoped fail-fast isolation, v1 pair, deferred trigger probe

**Status**: Accepted · **Date**: 2026-08-31

## Context

`/acs:create-quality` and `/acs:create-operations` are independent
product-level skills, each with its own planner/executor/verifier triad
(ADR-0011 §1/§3). Neither reads the other's output, they write disjoint doc
directories (`docs/quality/` vs `docs/operations/`), and
`create-operations/SKILL.md` already documents itself as usable "alongside
`/acs:create-quality`" — yet a consumer had to run them one at a time.
MAR-1 adds an orchestration path that detects when two or more independent
doc-bootstrap skills have their upstream prerequisites satisfied and spawns
them in parallel, while every fanned-out skill keeps its own reflection
cycle, hooks, and gating unchanged (ticket AC-1, AC-2).

Four hard constraints bound every option considered: (A) no acs subagent
may hold both `Agent` and `Skill` tools — the no-sub-subagent invariant is
stated three times in this repo (`plugins/acs/docs/INTERNALS.md`,
`docs/requirements/functional/reflection.md`, and per-skill prose); (B)
`/acs:code`'s parallel-spawn pattern parallelizes *agents* from one
coordinator context, not *skills* — nothing in this runtime is shown to run
two `Skill`-tool loads concurrently; (C) the single working tree is the
real serialization point — both skills demand a clean tree and
`git checkout -b` before the first executor writes; (D) `/acs:ship` cannot
host this and explicitly refuses `flow: "product"` tickets, and there is no
single shared ledger a `/acs:ship`-style walk could read, because each
fanned-out leg writes its own `pipeline-state.json` in its own partition.

The design (`design.md`, MAR-1) resolved eight decision points (D1–D8) plus
four sub-decisions (D3.2, D4.1, D4.2, D4.3) against these constraints. The
design's own draft proposed recording them as seven separate ADRs
(0084–0090), one per top-level decision. The user overrode that draft
(clarification C-16): this ticket records all eight decisions' outcomes as
**one** consolidated ADR, because no acceptance criterion or test
distinguishes "seven ADRs" from "one ADR" — `docs/adr/README.md`'s only
enforced invariant is bidirectional index completeness
(`tests/acs/test_doc_fact_pins.py::AdrIndexCompletenessTest`) — and one ADR
carries the same decision content at a fraction of the doc surface.

## Decision

**D1 — Detection/orchestration location: a new unhooked umbrella skill,
`/acs:create-docs`.** Follows the `/acs:ship`/`/acs:test`/`/acs:release`
precedent of unhooked coordinators with zero planner/executor/verifier
subagents of their own. Rejected: a fan-out section inside `/acs:ship`
(directly contradicts its product-flow refusal and its "run steps
sequentially" rule); documenting a manual concurrent recipe with no
orchestrator (does not satisfy AC-1's requirement for an actual
orchestration path).

**D2 — Parallelism mechanism: phase-level interleave in one coordinator.**
The umbrella invokes each leg's Start **sequentially** as genuine
`Skill`-tool calls, so the real `PreToolUse(Skill)` gate fires per leg
exactly as it does standalone. Once both legs have minted their delivery
ticket, the umbrella drives both legs' reflection loops together by
spawning each phase's **existing** planner/executor/verifier subagents in
parallel batches from one coordinator message — reusing `/acs:code`'s
parallel-executor/multi-lens-verifier mechanism verbatim. Accepted cost:
the umbrella's own SKILL.md must re-describe (cite, never restate) each
leg's reflection-loop, Delivery, and Finish sections, since a `Skill`-tool
load has no yield point that would let the loaded skill drive itself to
completion mid-interleave. Rejected: a new orchestrator-agent class holding
both `Agent` and `Skill` (breaks constraint A, and depends on the unverified
runtime property that `PreToolUse(Skill)` fires for a Skill call made from
inside a subagent); a worktree + headless session per leg (no existing acs
precedent for a coordinator spawning and awaiting another session, and does
not remove the two repo-level unguarded writers addressed by D5.1).

**D3 — Git delivery: one worktree per leg, entered at each leg's Branch
step (before Execute).** Each leg's clean-tree + `git checkout -b`
precondition is satisfied by construction; neither skill's own SKILL.md
changes. The worktree is given a generic, skill-scoped directory name (not
ticket-id-named, since the delivery ticket id does not exist until
`skill-start.py --allocate` runs, in the session checkout per D3.2; only
after that does the umbrella enter the worktree and name the git branch
with the minted ticket id).
**Sub-decision D3.2 — `skill-start.py` runs in the session checkout, not
the worktree.** This keeps the session marker's `checkout_id` matching the
`PreToolUse(Skill)` envelope's, so each run stays fully threaded
(`session_id`/`transcript_path`/`checkout_id` present, tokens and cost
measured); the cost is that the per-checkout session pointer and session
marker are genuinely shared between the two legs under this placement — a
labeled, display-level degradation (below), not a wrong-ticket write. Git
delivery itself (`git checkout -b`, commit, push, `gh pr create`) still
runs with cwd = each leg's own worktree, so the clean-tree precondition
holds per leg exactly as under standalone delivery. Rejected: serializing
delivery only in one tree (falsifies the "clean working tree" precondition
for the second leg); one shared branch and one combined PR (couples the two
legs' fate, contradicting AC-3's failure isolation and each skill's own
docs-only-PR-per-ticket contract); running `skill-start.py` inside the
worktree (D3.2 rejected option — resolves a different `checkout_id` than
the envelope's, the session marker is rejected on mismatch, and the run
degrades to zeroed tokens / `cost_usd: None` on both legs for no
measurement benefit).

**D4 — Dependency/eligibility declaration: an `acs_lib.py` table plus pure
helpers.** `DOC_BOOTSTRAP_DEPENDENCIES` (a skill → its declared upstream
doc-bootstrap dependencies, tagged `hard`/`soft`), `DOC_BOOTSTRAP_SETTINGS_KEY`
(explicit skill → settings-key map, never string-built), and a pure
`fanout_batches(settings, tickets_index, checkout_root)` helper sit beside
the existing `PRODUCT_SKILLS` table — matching ADR-0001's deterministic/
judgment split and giving AC-5's "declared, not inferred" a concrete,
unit-testable home. **D4.1 — eligibility needs both** doc-set presence on
disk (has this doc set ever shipped) **and** the absence of an open
delivery ticket for that skill in `tickets-index.json` (is a batch already
in flight) — either signal alone is blind to one real case the other
covers. **D4.2 — "present on disk" is a per-skill sentinel file**
(`os.path.isfile` on each skill's own first output-contract file, e.g.
`test-strategy.md` for `create-quality`), mirroring the existing
`_require_architecture_doc_set` precedent, chosen over a directory-non-empty
check because it fails toward safe re-bootstrapping rather than silently
skipping a doc set whose directory exists but was never actually produced
by the skill's own contract. **D4.3 — the dependency map is tagged, not
flat**: `hard` gates eligibility outright; `soft` only excludes a
candidate from the *same batch* as an eligible soft peer, never from
eligibility itself. No hard edge exists in today's doc-bootstrap set; the
one soft edge is `create-standards` → `create-principles`. Rejected:
declaring the dependency in each SKILL.md/agent frontmatter (a gate-shaped
fact in prose, unverifiable except as substring matching); declaring it in
`.acs/settings.json` (makes a pipeline invariant consumer-editable, unlike
every other edge in the conformance chain); a flat undifferentiated
dependency list (cannot distinguish a hard edge from a soft one).

**D5 — Ledger bookkeeping: no new ledger; each leg's own
`pipeline-state.json` is the resume record.** Each leg's own skill-start/
post-hook already writes its own `pipeline-state.json` with
`flow: "product"` and the correct step name; the umbrella re-derives what
remains by re-running D4.1's detection, and a partially-failed batch is
resumed **per leg**, via that leg's own standalone invocation — not through
the umbrella. This restates AC-4's literal "so `/acs:ship`'s existing
resume logic works correctly" against the fact that `/acs:ship` never
drives product-flow tickets in the first place: each leg's own standalone
resume already works unchanged, and the umbrella's own "resume" is
"re-run the eligibility predicate," not a ship-style ledger walk. Rejected:
a new fan-out batch record entity (disproportionate machinery — a new ER
shape, a new schema file, a new unguarded writer to make concurrency-safe —
for a v1 batch of exactly two legs); extending `/acs:ship` to walk the
product flow (directly reverses its explicit refusal of `flow: "product"`
tickets). **Sub-decision D5.1 — guard the two real unguarded writers.**
`update_index` and `update_metrics` (repo-level `tickets-index.json` /
`metrics.json`, shared even across separate worktrees of the same repo
because they key off `repo_id` alone) gain the same `O_EXCL` spin-lock
pattern already proven around `allocate_ticket_id`'s read-modify-write —
the only option whose safety does not depend on a *different* decision
(D2's single-threaded coordinator) never being revisited. The cost cursor
(`cost_sampler.py`) is explicitly **not** given the same guard
(user-confirmed): a race there degrades to a documented, disclosed
`cost_basis: "unavailable"` on the losing leg, never silent data loss or a
fabricated figure, keeping this ticket's blast radius inside `acs_lib.py`
as scoped.

**D6 — Failure isolation: per-leg, with one narrowly-scoped fail-fast
carve-out.** A failed leg (hook block, verifier cap, a lock held by another
session) leaves the other leg's run, PR, and ledger untouched; the
umbrella reports per-leg status and per-leg resume commands. The one
carve-out: both legs share exactly one precondition,
`_require_architecture_doc_set`, checked at each leg's own Start. Because
the two Starts already run sequentially (D2), if leg A's Start fails on
that shared gate the umbrella already knows leg B's identical gate would
fail too, and can report one message ("architecture doc set missing —
neither leg attempted") instead of spending a second Skill-tool call and a
second delivery ticket on a guaranteed-identical failure. This carve-out is
scoped **exclusively** to that one provably-shared precondition; every
other failure class falls straight through to per-leg isolation.

**D7 — v1 eligible set: exactly the pair, `create-quality` +
`create-operations`.** Matches the ticket's stated DoD and AC-1's literal
scope. A third independent skill becomes eligible via a data change to
`DOC_BOOTSTRAP_DEPENDENCIES` and to the declared v1 tuple
`DOC_BOOTSTRAP_FANOUT_V1`, not a code change. Generalizing to an N-way
batch (`create-principles`, `create-standards` under its soft dependency,
`create-requirements`'s interactive greenfield-elicit mode) before the
2-way mechanism has run in production would multiply every concurrency
hazard for a win this design cannot yet measure — deferred, not rejected.

**D8 — No `s04` trigger probe ships with `/acs:create-docs`; the gap is
recorded as a third deferred entry under PRD G8's existing
CI-guardrail-follow-up clause**, alongside `create-requirements` and
`docs-sync` (user-confirmed, same precedent those two most recent new
skills already used). Shipping the probe now would cascade into nine
surfaces and five live-derived test assertions across `evals/`, and risks
turning two already-green paid probes (`create-quality`,
`create-operations`) red against a new, closely overlapping description; no
test enforces `s04_cases == n_skills`, so this is a stated policy choice.
`/acs:create-docs`'s routing stays unprobed until the deferred CI-guardrail
follow-up lands.

## Consequences

- One new unhooked skill, `plugins/acs/skills/create-docs/SKILL.md`, with
  no dedicated agent files; skill count 24 → 25.
- `acs_lib.py` gains `DOC_BOOTSTRAP_DEPENDENCIES`, `DOC_BOOTSTRAP_SETTINGS_KEY`,
  `DOC_BOOTSTRAP_SENTINEL`, the declared v1 tuple `DOC_BOOTSTRAP_FANOUT_V1`,
  pure `doc_set_present_on_disk`/`fanout_batches` helpers, and an `O_EXCL`
  guard on `update_index`/`update_metrics` — a small, testable change to the
  most-depended-on module, benefiting every future parallel path in acs, not
  just this one.
- Four skill-name mirrors (`acs-messages.xsd`, `skill-state.schema.json`,
  `clarifications.schema.json`, `validate_xml.py`) gain `create-docs` in the
  same change as the skill directory.
- No new state entity, no settings-schema change, no new hook scripts, no
  new agent files: `docs/architecture/hld/data-model.md` and every existing
  gate script are untouched.
- Zero change to `create-quality/SKILL.md` or `create-operations/SKILL.md`,
  their agents, or their gates — every invariant either skill already
  declares is preserved by construction.
- Under D3.2's shared-`checkout_id` placement, the per-checkout session
  pointer and session marker are shared between the two legs — an accepted,
  display-level degradation (the statusline shows one of the two legs; the
  session marker still describes a genuine current session for both) and
  never a wrong-ticket write, since every downstream consumer is given the
  ticket id explicitly. The cost cursor's same-`checkout_id` race is
  disclosed via `cost_basis: "unavailable"` on the losing leg, never
  fabricated or zero-padded. Transcript role attribution likewise
  under-reports each leg's coordinator bucket and over-reports its subagent
  roles roughly 2x under this same-session interleave — a genuine
  intra-session cross-contamination gap in a decision of record, carried to
  `/acs:docs-sync` as a boy-scout drift item against ADR-0082's consequences.
- Epic-child parallel fan-out (manual, one worktree per child via
  `/acs:ship <child-id>`) is unchanged and untouched by this decision — it
  parallelizes tickets sharing one design, not product-level skills sharing
  no ticket and no design step.
- This ADR is recorded as one consolidated record rather than the seven the
  design originally drafted (C-16, user-confirmed): every decision above
  (D1–D8, D3.2, D4.1–D4.3) is in force from this single ADR's acceptance.
