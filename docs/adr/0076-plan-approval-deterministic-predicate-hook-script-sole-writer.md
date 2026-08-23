# 0076 — Coordinator plan approval: a deterministic predicate, recorded by a hook script, never gated this release

**Status**: Accepted · **Date**: 2026-08-23

## Context

MAR-69 slices 1a/1b/2 made `/acs:code`'s plan artifact a single per-ticket
`plan.md` (MAR-70), written exactly once per run before the loop (MAR-71,
slice 1b), and lane-conditionally authored — `code-planner` on
STANDARD/COMPLEX, the coordinator itself on TRIVIAL/SMALL (MAR-72, ADR
0074) — but nothing checked the plan artifact's conformance to its own
contract. Slice 4 (MAR-69) wants the verifier to anchor on an approved plan,
which requires an approval that cannot be forged by the same LLM whose work
it certifies — an approval must not be an LLM self-assertion (`ticket.json`
acceptance criteria and description, this ticket, MAR-73).

## Decision

1. **D-1 — approval is a pure deterministic predicate.** Approval is
   computed by `acs_lib.plan_approval_eligible(plan_text, settings,
   fold_active)` over the plan artifact's own bytes plus
   `settings.test_coverage_percent` — pure, no I/O, no clock. The digest
   (`plan_sha256`) is computed inside the predicate itself, not passed in by
   the caller, so a verdict can never be paired with another plan's bytes.
2. **D-2 — the sole writer is a script.** `plan-approval.py` is the ONLY
   writer of `<partition>/phases/code/plan-approval.json` — never a
   subagent's `Write` tool, never the coordinator's own `Write`. This is
   guarded by `tests/acs/test_plan_approval.py`, which asserts no file under
   `plugins/acs/agents/` names the record or the `plan_approved` key, and
   that `code/SKILL.md` forbids a subagent `Write` of the record.
3. **D-3 — recorded, not gated, this release.** `/acs:code` copies the
   script's printed `plan_approved` value verbatim into `result.json`'s
   `states.plan_approved` and the script mirrors it into `code-state.json`.
   `/create-pr`'s gate remains `code-state.states.verifier_passed == true`
   alone; nothing reads `plan_approved` as a gate this release.
4. **D-4 — STANDARD/COMPLEX only.** The script recomputes the lane via
   `derive_lane`, never the cached `ticket.lane`, and no-ops with
   `plan_approved: false` (no record written) on TRIVIAL/SMALL — mirroring
   ADR 0074's D-2 lane-source rule.
5. **D-5 — once per approved plan digest.** A second invocation over the
   same `plan.md` bytes (matching `plan_sha256` on an already-`eligible`
   record) is a no-op that re-asserts the existing verdict — idempotent on
   resume. A revised `plan.md` (a new digest) writes a fresh record.
6. **D-6 — `--plan` containment.** An explicit `--plan` must resolve
   (realpath) within `<partition>/phases/code/`; the script rejects an
   escaping path with clean stderr and exit 2, writing no record.

## Consequences

- The predicate's required-section/fold-section/clause lists
  (`PLAN_REQUIRED_SECTIONS`, `PLAN_FOLD_SECTIONS`, `PLAN_FOLD_CLAUSES`) must
  be kept in sync by hand with `code/SKILL.md`'s plan contract — they are a
  duplicated, not derived, mirror.
- The predicate deliberately *mirrors* `structure_lint`'s heading-scan and
  ambiguous-name safeguard rather than importing it, so `acs_lib.py` stays
  import-free and pure (no first-import disk touch). A future change to
  `structure_lint`'s semantics does not automatically propagate here.
- An ineligible plan is visible (the script prints its failing checks) but
  non-blocking today — a plan that never becomes eligible surfaces only at
  slice 4, when the verifier starts anchoring on this record.
- Relationship to **ADR 0001** (deterministic-vs-judgment split): this
  decision instantiates that invariant in a new place — approval is
  deterministic-layer work, never subagent judgment.
- Relationship to **ADR 0004** (reflection trio; verifier anchors on gated
  contracts): its verifier-anchoring text will need amending when the
  verifier starts anchoring on `plan_approved` — explicitly **not** by this
  ticket, but by **slice 4 / MAR-74**.
