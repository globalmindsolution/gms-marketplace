# 0053 — Release versions are modeled as an additive `roadmap.md` mapping table, decoupled from the cut skill

**Status**: Accepted · **Date**: 2026-07-12

## Context

Alongside the cut-release capability (MAR-129), the epic MAR-128 also scopes
a first-class release-version capability (capability b): an explicit
version → milestone/epic mapping in the roadmap doc set, so every committed
milestone resolves to exactly one release version (G17's 0-orphan-milestones
metric).

## Decision

**Option A — an additive `roadmap.md` "Release versions" mapping
table/section maintained by `/acs:create-prd`**, mapping each release
version to the milestone(s)/epic(s) it delivers (e.g. `v0.4.2 → Wave 3 →
{MAR-128}`). The cut skill (`/acs:release`, ADR 0050/0051) never resolves
ticket→version through this table — it reads the merged-ticket archive/
`git log` directly (ADR 0051) — keeping the two capabilities decoupled.

## Alternatives considered

- **Option B — a structured version-object file (e.g. `.acs/releases.json`).**
  *Rejected*: heavier new schema/coupling surface with no current consumer.
- **Option C — inline per-milestone annotations.** *Rejected*: no single
  scannable index for the G17 100%-mapping verifier check.

## Consequences

- A bug or gap in the new roadmap table can never break a release cut — the
  decoupling holds in both directions.

**Scope note (record-only in this ticket).** This ADR records **only** the
accepted decision, for a clean, contiguous 0050-0053 block. The decision's
subject matter — the `roadmap.md` mapping table content itself, the
`create-prd/SKILL.md` executor/verifier duty extensions, and the
`create-prd-executor.md`/`create-prd-verifier.md` agent-charter mirrors — is
capability (b) and ships in **MAR-130**, not MAR-129.
