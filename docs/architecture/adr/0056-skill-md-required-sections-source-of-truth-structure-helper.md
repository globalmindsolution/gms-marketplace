# 0056 — SKILL.md-declared `required_sections` as the single source of truth + deterministic structure-conformance helper

**Status**: Accepted · **Date**: 2026-07-14

## Context

Structure/section conformance is not deterministically enforced across the
acs doc-producing skills. `create-prd-verifier.md` already reads a
`required_sections` constraint and checks presence mechanically, but the
other producer verifiers either inline their heading list
(`create-design-verifier.md`) or use an LLM "covers X" judgment
(`create-principles-verifier.md`, `create-standards-verifier.md`,
`create-quality-verifier.md`, `create-operations-verifier.md`). None
deterministically checks presence + non-empty + skill-defined order, so a
generated doc can silently drop or leave empty a required section (PRD G36,
`prd.md:202`; C-20/C-21).

## Decision

Make each prose-doc SKILL.md's own declared `required_sections` list the
single source of truth for a new stdlib structure-conformance helper
(`plugins/acs/hooks/scripts/structure_lint.py`):

- **Source of truth (B1).** Each prose-doc SKILL.md declares
  `required_sections`; the coordinator passes that same list into the
  verify `<task>` as a `required_sections` constraint. The list the
  executor is instructed to write IS the list the verifier checks — no
  second, driftable copy anywhere. This generalizes the pattern
  `create-prd/SKILL.md` already ships (`required_sections` declared to the
  executor and consumed by its verifier).
- **Helper.** `structure_lint.py` mirrors `mermaid_lint.py`'s shape
  precisely: stdlib-only (`re`, `sys`, `collections.namedtuple`),
  read-only, a `Finding(source, line, rule, message)` namedtuple (the
  identical 4-field shape `mermaid_lint.Finding` uses), and
  `lint_structure`/`lint_file`/`main(argv)` functions. Given the declared
  section list, it reports `missing-section` (no matching heading),
  `empty-section` (heading present, no non-blank body before the next
  heading or EOF), and — only when `ordered=True`/`--ordered` is passed —
  `section-order` (two declared sections appear in the doc in the reverse
  of their declared relative order). Heading lines are matched by the
  bounded, ReDoS-safe prefix `^#{1,6} `. On any order ambiguity (a declared
  section repeats, or a heading text matches more than one declared entry)
  the helper relaxes to presence + non-empty for the ambiguous section(s)
  rather than false-blocking a legitimate reorder. CLI exit codes mirror
  `mermaid_lint.py`: 0 clean, 1 any finding, 2 usage error or unreadable
  file.
- **This ADR ships the helper unwired** — a sibling ticket wires the
  helper into the 7 prose-doc verifiers as a blocking `structure` dimension
  and adds an advisory `audience-style` dimension (ADR 0057).

## Alternatives considered

- **B2 — a separate per-skill manifest/schema file** (e.g.
  `required_sections.json`). Machine-validated, one place, but a **second**
  source of truth that can drift from the SKILL.md prose the executor
  actually reads, plus a new artifact + loader with no added safety over
  B1. Rejected.
- **B3 — hardcode the required-section list inside each verifier.**
  Simplest per file, but seven independent copies to keep in sync with
  seven SKILL.md — drift-prone, and defeats the "the checked list is the
  written list" guarantee. Rejected.

## Consequences

- No drift: a conforming doc — one that follows the SKILL.md's own
  instructions — can never be false-blocked by the structure floor, because
  the checked list and the written list are the same text.
- The verifiers that currently inline their heading list or use an LLM
  "covers X" judgment (create-design, create-principles, create-standards,
  create-quality, create-operations) must be converted to the
  declared-constraint pattern — bounded, mechanical work, done by the
  sibling ticket that wires this helper.
- No new runtime dependency: `structure_lint.py` is stdlib-only (`re`,
  `sys`, `collections`) — no Node, no network, read-only.
- `structure_lint.py`'s `--sections` delimiter is semicolon (`;`), not the
  pipe originally sketched, so the SKILL.md's already-semicolon-delimited
  `required_sections` string (`create-prd/SKILL.md`'s existing convention)
  passes through verbatim with zero conversion — documented as an
  intentional, flagged deviation where the helper's contract is specified.
