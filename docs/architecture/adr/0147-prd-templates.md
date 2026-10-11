# 0147 — The PRD doc set is written from templates

**Status**: Accepted · **Date**: 2026-10-11

**Amends**: [0142](0142-prd-hub-and-feature-prds.md) (the hub's and a feature
PRD's sections come from a template, not a list fixed in the skill).

## Context

`/acs:create-prd` wrote the hub with eight sections and each feature PRD with
six, both lists spelled out in its SKILL.md, its agents and
`prd_feature_check.py`. A team with its own PRD shape — a Rollout section, a
Risks section, different names — could not use it, and the lists had four
copies to keep in step. The tech design (`design-default`), the tickets, the PR
body and the audit reports already come from templates a repo can replace in
`.acs/templates/`.

## Decision

1. **Two built-in templates** ship in the plugin's `templates/`: `prd-default`
   (the hub) and `prd-feature-default` (a feature's own PRD), each a title, the
   `## ` sections and HTML-comment guidance for the author.
2. **A repo replaces either** with `.acs/templates/<name>.md`, checked first.
3. **The template's `## ` headings are the required sections.** `acs.py prd
   template` resolves both templates and prints each one's path and sections;
   the coordinator passes them as `required_sections` and
   `feature_required_sections`, so the authors, the reviewer and the structure
   floor read one list. A new document starts from its template; the guidance
   comments are not kept.
4. **A feature template keeps `Goals served` and `Requirements`.** Tickets link
   a feature's `R<n>` ids (ADR-0144) and its implemented status is derived from
   them (ADR-0146), so `acs.py prd template` refuses a template that drops
   either — as it refuses one with no section or a repeated one.
5. **The roadmap has no template**: its shape is a grammar `acs.py roadmap
   status` and `roadmap_check.py` parse (ADR-0145).

## Consequences

- A team adds, renames or reorders PRD sections by committing a template; the
  structure gate follows it with no setting to change.
- The built-in templates carry exactly the sections the skill required before,
  so a repo without `.acs/templates/` sees no change.
