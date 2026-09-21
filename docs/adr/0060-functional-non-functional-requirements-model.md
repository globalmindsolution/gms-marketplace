# 0060 — Functional/non-functional settings-aware requirements MODEL

**Status**: Accepted · **Date**: 2026-07-15

## Context

`docs/requirements/` (`settings.requirements_path`, default
`docs/requirements`) is the living behavioral contract `/acs:code` accretes
into ticket by ticket: today it is a flat set of per-topic files that MIX
behavioral requirements (what the software does) and quality requirements
(performance, security, reliability, portability, operability) in the same
file. G37 folds in a requirement to separate the two: a **functional/**
subfolder (one file per feature — behavior) and a **non-functional/**
subfolder (one file per NFR item — quality), settings-resolved so the split
works on any consumer repo, not just this marketplace (C-20, consumer-repo
generality).

A second, narrower question follows: how does `/acs:code`'s
requirements-merge step (and the future `/acs:create-requirements` skill,
MAR-143/144) decide which subfolder a given requirement belongs in? Prose
requirements are inherently judgment; a deterministic classifier would be a
new runtime component fighting the stdlib-only / no-new-dependency
constraint.

## Decision

**Settings-key shape (Decision B-revised).** Add a sibling
`requirements_layout` object to the existing `requirements_path` string key
in `plugins/acs/schemas/settings.schema.json`:

```json
"requirements_layout": {
  "functional_subdir": "functional",
  "non_functional_subdir": "non-functional"
}
```

`requirements_path` stays a plain string — no `oneOf(string, object)`
promotion, no breaking change for any existing string reader. The top-level
schema keeps `additionalProperties: true`, so the new key is
forward-compatible. Resolution: `<requirements_path>/<functional_subdir>/`
and `<requirements_path>/<non_functional_subdir>/`; an absent key, or an
absent sub-key, resolves to the defaults `functional`/`non-functional`, so a
zero-config repo keeps working unchanged.

**Classification (Decision E-i).** Both producers that write into the model
— `/acs:code`'s requirements-merge step today, and the future
`/acs:create-requirements` skill — classify each requirement by
**producing-skill LLM judgment against a written rubric**, carried verbatim
in each skill/agent's own prose so the two classify identically:

- **FUNCTIONAL** — a requirement describing a BEHAVIOR the software
  performs. "The system DOES X." → `functional/<feature>.md`.
- **NON-FUNCTIONAL** — a requirement constraining a QUALITY of how the
  software behaves. "The system does it WITHIN/UNDER constraint Y." →
  `non-functional/<item>.md`.
- **Tie-break** — a requirement that is genuinely both defaults to
  **functional**, with a one-line cross-reference from the paired
  non-functional file, keeping routing deterministic at the seam.

`/acs:code`'s requirements-merge step (`code/SKILL.md`, `code-executor.md`)
now classifies-then-routes each merged requirement into the resolved
subfolder; the additive, per-feature-area, no-overwrite merge semantics are
unchanged — only the target subfolder selection is new. The code-verifier's
documentation dimension (`code-verifier.md`) treats a requirement written to
the wrong subfolder, or outside `requirements_layout`'s resolved subfolders,
as a blocking finding.

This ADR scopes ONLY the foundation MAR-145 ships (the settings key + the
`/acs:code` subfolder-routed merge); the `/acs:create-requirements` skill
itself is MAR-143/144's, recorded separately (ADR 0058, ADR 0059).

## Alternatives considered

- **`requirements_path` promoted to `oneOf(string, object)`.** Rejected — a
  breaking type change for every existing string reader, for no functional
  gain over a sibling additive key.
- **A new, richer universal per-file template** (fixed sections regardless
  of functional/non-functional). Rejected — would create a second
  requirements shape diverging from what `/acs:code` already accretes,
  reintroducing drift.
- **Deterministic keyword/heuristic classifier** for functional-vs-NFR.
  Rejected — brittle over free-form prose, and a new runtime component
  fighting the stdlib-only / no-new-dependency constraint. Its idea survives
  only as example keywords inside the written rubric.
- **Require the ticket/AC to declare its own category.** Rejected — pushes
  classification onto every ticket author and breaks the ticketless
  brownfield extraction path.

## Consequences

- `requirements_layout` is purely additive/opt-in: a repo with no
  `requirements_layout` block, or on a version of acs before this ADR, keeps
  resolving to `functional`/`non-functional` — no settings edit required, no
  behavior change for existing merges into files that predate the split.
  Physically reorganizing this repo's own flat `docs/requirements/*.md` set
  into the new subfolders is a separate, sequenced change (does not land in
  this ADR's foundation).
- The rubric is carried verbatim (not paraphrased) in both `code/SKILL.md`
  and `code-executor.md` so classification stays repeatable across the two
  merge-routing prose copies, and the future `/acs:create-requirements`
  skill inherits the same wording rather than drifting.
- Requirements stays a **living contract** alongside the verified
  conformance chain (`PRD → architecture → principles → standards → design
  → specs → code`), not a new chain link — this ADR adds no
  requirements-conformance verifier dimension and does not touch the chain
  line in `docs/architecture/lld/contracts.md` (see ADR 0059 for the
  chain-clarifying note itself).

## Amendment — v0.5.0 (the implementation-pipeline redesign)

The settings-key shape (Decision B-revised) and the classification rubric
(Decision E-i) are unchanged: `requirements_layout` is still a sibling object,
`requirements_path` is still a plain string, and both producers still classify
by LLM judgment against the rubric carried verbatim in their own prose.

Two producer names in the Decision aged. `/acs:create-requirements` is no
longer "future" — it shipped, and it is one of the two producers. `/acs:code`'s
requirements-merge step is the other; the doc delta rides the changeset as
[0007](0007-living-docs-by-induction.md) has it.

The Consequences' "the code-verifier's documentation dimension
(`code-verifier.md`)" is now `/acs:review-code`'s **lens E**
([0099](0099-review-is-a-step-not-a-phase.md)): the `code-verifier` agent is
gone, and lens E judges the change's own documentation and blocks on it. The
treatment this ADR asked for — a requirement written to the wrong subfolder is
a documentation finding, not a silent pass — is unchanged, and now applies on
every delivery path rather than only where a verifier was spawned.
