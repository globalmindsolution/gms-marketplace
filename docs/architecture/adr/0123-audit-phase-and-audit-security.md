# 0123 — An Audit phase: read-only, report-first skills, with `/acs:audit-security`

**Status**: Accepted · **Date**: 2026-10-04

**Amends**: [0118](0118-discovery-design-development-phases.md) (a fourth phase beside
Discovery, Design and Development) and
[0122](0122-design-versions-and-gap-detection.md) (`/acs:audit-design` moves
into it).

## Context

`/acs:audit-design` (ADR-0122) did not fit the three phases: it designs nothing,
tickets nothing by itself and builds nothing, yet it is not plumbing like `/acs:setup`
either. It answers "how far is what we have from what it should be", on demand and at
any point in a product's life. A security audit is the same kind of question, asked
against a different standard — and the repo had no skill for it: `/acs:review-code`'s
lens B judges the security of one changeset's hunks, never the repository, its
secrets, its dependencies or its threat model.

## Decision

1. **The Audit phase** groups skills that read the repository against a standard and
   report. An audit skill is **read-only** (it never edits code, documents or
   configuration), runs **without a ticket**, can run at any time, and writes its
   report to the workspace. What happens next is the user's choice through the
   Discovery and Development skills. It holds `/acs:audit-design` and
   `/acs:audit-security`.
2. **`/acs:audit-security`** audits four categories, each by its own **auditor**
   (role kind `survey`) in parallel: `code` (OWASP Top 10 weakness classes with their
   CWE, sliced per code area), `secrets-config` (hard-coded credentials and insecure
   configuration, including CI), `dependencies` (only through the scanners the repo
   already has installed; never installed by acs, never a CVE named from memory) and
   `threat-model` (the code against `hld/data-flow.md` and `hld/cross-cutting.md`,
   when the architecture set has them).
3. **Auditors raise candidates; adjudicators decide.** Every candidate gets one
   fresh-context **adjudicator** (role kind `judge`) that sees only that finding and
   is prompted to refute it, defaulting to refuted when uncertain — the
   `/acs:review-code` pattern (§3.6). A confirmed finding carries an adjudicated
   severity and a `resolved_when`; a `needs-context` one is carried as advisory.
4. **Report only.** The output is a severity-ranked report (`critical` → `low`, each
   with CWE, `file:line`, evidence, exploit scenario and fix guidance). It files no
   ticket and emits no SARIF; a category that could not be examined is reported as
   uncovered, never as clean; a secret's value never appears in any artifact.

## Consequences

- Skill count +1; one new agent role (`auditor`), and the existing `adjudicator` role
  gains a second owner. Two agent files, one hook pair.
- Both audits run without a ticket: `acs step start` opens (or resumes) a run over the
  invocation and the post-hook concludes it (`AUDIT_SKILLS`).
- Each audit writes its report from a template (`templates/<skill>-report.md`, or the
  repo's `.acs/templates/` copy). The template is the contract: its `## ` sections, in
  order, and the ones marked `acs:count <key>`, whose `### ` entries are counted. The
  post-hook refuses a completed audit whose report breaks it and derives
  `states.audit`'s counts from the report (`acs_lib.audit_report`).
- The README and the docs group skills as Discovery · Design · Development · Audit ·
  Utility.
- A repo with no installed scanner gets no CVE coverage from acs, and the report says
  so. Adding SARIF or ticket creation later is an amendment, not a change to the
  contract the report already has.
- `/acs:audit-design` keeps offering to ticket its gaps: a design gap is planning
  input, which the team decides on there and then; a security finding is not ticketed
  by acs because its triage and disclosure belong to the team's own process.
