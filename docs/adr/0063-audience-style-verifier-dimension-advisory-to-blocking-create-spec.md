# 0063 — Audience-style verifier dimension: ADVISORY → BLOCKING, extended to create-spec

**Status**: Accepted · **Date**: 2026-07-16

## Context

ADR 0057 added an `audience-style` verifier dimension to the doc-producing
skills and made it **advisory** (`severity="info"`, never blocking) — a
deliberate, load-bearing exception to those verifiers' otherwise all-blocking
rule. It chose advisory because an LLM register judgment can misfire, and a
flaky subjective block across many skills was judged too high-risk at the time
(ADR 0057 alternative C-sub-2, rejected).

The G38 readability goal (PRD, MAR-149 epic design Decision A) now asks for the
audience gate to actually hold the line: "audience-appropriate style" is an
acceptance criterion, and a surfaced-but-ignorable finding does not enforce it.
The epic design settles the mechanism — flip the existing dimension to blocking
on the **8** producer verifiers that declare an `audience_style_profile`
(create-design, create-prd, create-architecture, create-requirements,
create-standards, create-quality, create-operations, create-principles),
extend it net-new to create-spec, and pay down ADR 0057's flakiness concern
with a waiver path rather than by staying advisory. create-project stays N/A
(it scaffolds a greenfield repo and declares no audience profile).

## Decision

**Reverse ADR 0057's advisory carve-out.** The `audience-style` dimension is
**BLOCKING**: an unwaived register mismatch is emitted as
`<finding severity="blocking" dimension="audience-style">`, exactly like every
other dimension. The advisory carve-out sentences ADR 0057 added — the "ALL
findings block **except** the advisory audience-style dimension" hard-rule
clauses, the "Advisory observations … **except** the sanctioned
`severity="info"` audience-style finding" report-notes, and create-design's two
preamble/findings-format anchors — are reversed in all 8 producer charters so
no sentence still exempts the dimension.

**Keep the anchored-profile mechanism (ADR 0057's hybrid).** The judgment is
still anchored to each skill's declared `audience_style_profile` rubric, not the
model's unanchored opinion. No deterministic `audience_lint` heuristic is
introduced — ADR 0057 rejected style heuristics on the merits and this decision
does not re-open that (epic design Option A2, rejected).

**Add a clarify-ledger waiver path.** The AC's "0 **unwaived**
audience-mismatch findings" wording presumes a waiver concept. It reuses the
existing clarification/assumption ledger, with no `clarify.py` change: a
register the coordinator has recorded as a deliberate choice via
`clarify.py add --skill <skill> --source assumption --rationale "<why the
register is deliberate>"` — surfaced to the verifier in `<context>` on
iteration 2+ — is **waived** and emitted as `severity="info"`, which does not
block. So each dimension body deliberately carries both severities: `blocking`
for the unwaived default, `info` for the waived case. The pass bar is 0
unwaived audience-mismatch findings.

**Extend to create-spec (net-new).** `create-spec/SKILL.md` declares
`<constraint name="audience_style_profile">engineers (implementation-contract
prose)</constraint>` and forwards it into the execute and verify tasks;
`create-spec-verifier.md` gains a blocking `audience-style` dimension judged
against that profile, with the same waiver clause. create-spec-verifier's
pre-existing "ALL findings block" rule already covers it, so no carve-out is
added. This decision scopes create-spec-verifier's and create-design-verifier's
edits to audience-style ONLY — the `structure_lint` dimension for create-spec is
owned by a separate decision (epic design Decision C) so it appends cleanly.

## Alternatives considered

- **Stay advisory (ADR 0057 status quo).** Zero flakiness risk, but leaves the
  audience-appropriate-style half of the readability goal unenforced — a
  surfaced finding a coordinator can ignore does not gate the doc. Rejected: it
  under-delivers the epic's explicit acceptance criterion.
- **A deterministic `audience_lint.py` helper** (reading-level scores,
  sentence-length limits, per-audience jargon lists), blocking and $0. Rejected:
  ADR 0057 already reasoned against deterministic style heuristics ("appropriate
  register does not reduce to a line-length or word-list check; heuristics
  misfire → false positives"), and it would add a hook script; the anchored-LLM
  judgment keeps register judgment where it belongs.
- **Blocking with no waiver.** Simplest rule, but a flaky subjective judgment
  could false-block a defensible register across 9 skills — the exact
  high-blast-radius risk ADR 0057 weighed. Rejected in favor of the anchored
  profile + ledger waiver, which records a defensible stylistic choice instead
  of hard-blocking it.

## Consequences

- A producer run that passed today under the advisory dimension can now RED on
  a register mismatch. This is an intentional behavior change, not a
  byte-identical no-op. The blast radius is paid down by three shipped
  mitigations: the anchored per-skill profile, the clarify-ledger waiver path,
  and the deterministic structure + line-length gates that remain the objective
  floor so audience-style carries only register/narrative judgment.
- The `audience-style` dimension body in each verifier now legitimately contains
  both `severity="blocking"` (unwaived) and `severity="info"` (waived) — the
  info case is the waiver mechanism, no longer the default.
- create-spec is gated on register for the first time: specs are held to an
  implementation-contract register for the /acs:code engineer.
- create-project remains permanently N/A — no audience profile, no dimension —
  re-locked by a negative contract test.
- ADR 0057 is superseded on the severity question; its hybrid anchored-profile
  mechanism is retained. The guard test
  `tests/acs/test_structure_audience_verifiers.py` is rewritten from asserting
  advisory to asserting the blocking contract, the create-spec net-new gate,
  the waiver clause, and the create-project N/A lock.
