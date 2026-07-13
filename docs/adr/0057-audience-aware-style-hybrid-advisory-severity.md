# 0057 — Audience-aware-style HYBRID mechanism, ADVISORY severity

**Status**: Accepted · **Date**: 2026-07-14

## Context

Structure conformance (ADR 0056) is a deterministic floor: are the required
sections present, non-empty, and in order? It says nothing about whether a
generated doc reads right for its actual audience — "the right register for
the viewer" (PRD G36; user guidance C-4: each doc-producing skill's output
has a different type of viewer — product/business readers for the PRD,
engineers/architects for the architecture set, reviewers for a design
decision, and so on). Judging register is not a presence/absence check; it
is a judgment call, and the 7 prose-doc verifiers are already LLM judges
making judgment calls on every other check dimension.

A second question follows directly from the first: if the audience-style
check is a judgment call, should a miss BLOCK the doc (like the deterministic
structure floor and MAR-137's diagram-lint gate) or only be surfaced? Six of
the seven prose verifiers already treat every finding as blocking by
convention; `create-design-verifier.md` states this most explicitly ("ALL
findings block — there are no advisory findings in this skill").

## Decision

**C1 — HYBRID.** Keep the deterministic structure floor (ADR 0056's helper)
as the objective, blocking gate, and add a separate `audience-style`
verifier dimension that judges register/style against a **declared**
per-skill audience/style profile — not the model's unanchored opinion. Audience
map: `create-prd` → product/business (plainer prose); `create-architecture` →
engineers/architects (technical, diagram-heavy); `create-design` → reviewers
(decision + trade-off narrative); `create-principles`/`create-standards` →
engineers (concise normative rules); `create-quality` → QA (test/verification
runbook register); `create-operations` → ops/SRE (runbook register). Each
profile is declared in the skill's own SKILL.md (`audience_style_profile`
constraint) and passed into the verify task, mirroring the structure floor's
own declared-constraint pattern (ADR 0056/B1) — so the subjective half of the
check is still anchored to a written rubric, not model whim.

**C-sub-1 — ADVISORY.** The `audience-style` finding is surfaced,
**non-blocking**: it always carries `severity="info"` (the acs-messages
schema's non-blocking severity value) and never `severity="blocking"`. Only
the deterministic structure floor, the diagram-lint gate, and each verifier's
pre-existing dimensions block. This is a **deliberate, load-bearing
exception** to `create-design-verifier.md`'s usual all-blocking rule — its
own hard-rule sentences (preamble and findings-format) are amended with an
explicit carve-out so no residual sentence contradicts the new advisory
dimension; the same carve-out is applied to the equivalent "ALL findings
block" sentence in the other 6 verifiers, so none of the 7 is left
self-contradicting.

## Alternatives considered

- **C2 — fully-deterministic per-doc-type style heuristics** (reading-level
  scores, sentence-length limits, per-audience jargon lists). Deterministic,
  no flakiness — but "appropriate register for engineers vs. business
  readers" does not reduce to a line-length or word-list check; heuristics
  misfire on valid prose (false positives), which is exactly the failure
  mode this epic's readability goal warns against. Rejected.
- **C3 — structure floor only, defer all style judgment.** Smallest, fully
  deterministic, zero flakiness — but drops the audience-appropriate-style
  half of the readability goal (an explicit acceptance criterion and the
  user's C-4 guidance). Under-delivers the epic. Rejected.
- **C-sub-2 — BLOCKING** (consistent with `create-design`'s existing
  all-blocking default; no special-case severity). Simpler rule, but a flaky
  subjective judgment could false-block a valid doc across all 7 skills — the
  high-blast-radius risk this epic's own risk register (R1) flags. Rejected.

## Consequences

- The `audience-style` dimension can be safely ignored by a coordinator that
  chooses not to act on it — a run with only `audience-style` findings and
  zero findings on every other dimension is still a PASS. This is an accepted
  trade-off (surfaced insight beats a flaky block), not an oversight.
- Every one of the 7 prose verifiers' "ALL findings block" (or equivalent
  "no advisory findings"/"never as findings") hard-rule sentence carries the
  carve-out naming this exception explicitly — `create-design-verifier.md`
  carries it at both of its two anchors (preamble and findings-format).
- The audience/style profile is a short, fixed phrase per skill (declared
  once in SKILL.md), not a tunable per-repo setting — keeping the mechanism
  simple and consumer-general; a consumer wanting a different register can
  amend the skill's own declaration, the same lever `required_sections`
  already uses.
