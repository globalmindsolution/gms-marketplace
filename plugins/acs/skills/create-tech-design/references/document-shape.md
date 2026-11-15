# The shape of `tech-design.md`

Read before the first designer task; the reviewer's `completeness`,
`structure` and `lld-consistency` dimensions judge exactly this.

`tech-design.md` is the hand-off document: what the team reads to approve the
change's design before implementation is planned. It decides, and it points —
the HLD and the feature's LLD stay the single home of their content; the tech
design snapshots the parts this change touches, linked at their versions, so
the reviewer of the hand-off sees the design the decision was made against.

## The document

```markdown
---
status: proposed
version: 1
tickets: ["SHOP-123"]
feature: bulk-import
---

# Tech design — <id>: <title>

## Decision & options
   The one-line decision statement FIRST — it becomes states.decision. Then
   ### Context (problem, scope, assumptions; binding constraints from the
   PRD, the HLD and the codebase), ### Options considered (>= 2 real options
   per major decision, #### Option A/B/..., each with how it works and
   explicit trade-offs against the NFRs and constraints — no strawmen),
   ### Rationale (why the chosen option wins, why the others lose, citing the
   user's answers where they settled a trade-off) and ### Decision records.
## HLD views affected
   One entry per hld/ view the change touches: a link to the view with its
   version and status (`[hld/c4-container.md](../../../hld/c4-container.md)
   v4, approved`), a snapshot excerpt of the part this change touches (the
   rows, elements or diagram lines — never the whole view), and either
   "conforms — no change" or the exact change the view needs. With no
   architecture set: "n/a — no architecture doc set; designed against the
   codebase".
## LLD
   One line naming the feature's LLD folder, then exactly these four
   subsections, each a snapshot of the feature's living documents in that
   category that this change touches — a link with the document's version
   and status, and an excerpt of the operations, entities, flows or
   components involved:
   ### API          lld/<feature>/api/<interface>.md
   ### Data         lld/<feature>/data/*.md
   ### Flows        lld/<feature>/flows/*.md
   ### Components   lld/<feature>/components/*.md
   A category with no document yet reads "none yet — run
   /acs:create-api-contract <id>" (Data: /acs:create-data-design, Flows and
   Components: /acs:create-flows), plus one line on what this change needs
   designed there. Never redesign an LLD document here: a shape the change
   needs and the document lacks is a "none yet"/"needs update" line naming
   the skill that writes it.
## NFRs
   Security and performance REQUIRED, concretely (authn/authz, data
   exposure, input handling; load, latency, volume with numbers or bounds),
   plus every other NFR that applies (availability, cost, operability,
   compliance).
## Risks
   Blast radius, affected tickets/components, risks with mitigations, and
   ### Rollout & migration — ordering, data/schema migration, feature flags,
   backward compatibility, rollback plan (or "single-step deploy, no
   migration" with justification).
## Open questions
   What the team should settle at review — each with its options and the
   ledger entry (`C-<n>`, open or assumed) — or "none".
```

**Epic vs story.** An epic fills every section. A story or task fills the
sections it needs; every other section — and every LLD subsection — still
appears, reading "n/a — <why>" (one line, a real reason), so the hand-off
always has the same shape. For an epic: design at epic level — children
INHERIT this design via cross-partition read in their /acs:code; never
duplicate or split it into child partitions. The design a child reads is the
EPIC's `tech-design.md`, resolved the same way (its design record under
`<architecture_dir>/lld/<feature>/<epic-id>/`, else its partition; a legacy
`design.md` when the epic was designed before ADR-0135).

**Links and versions.** Links are relative to the design record folder
(`../api/imports.md`, `../../../hld/c4-container.md`); a design kept local
links repo-relative paths. Each version and status is the one `acs.py design
check <doc>` prints at draft time — the reviewer re-runs it, and a snapshot
that names an older version than the document's current one is stale. A
document with no front matter is linked "unversioned".

**Version front matter (ADR-0122).** The block above is written ONLY by
`acs.py design init` / `design bump` (SKILL.md, artifact resolution) — the
designer writes the body below it and never touches it, and nobody edits it by
hand. `/acs:set-doc-status` moves it to `approved` once the team signs off.

## Decision records

The designer adds `### Decision records` under "Decision & options", listing
each accepted decision as a one-line ADR title and noting: "/acs:docs-sync
writes these as ADRs under `<adr_dir>` once the changeset exists."
`/acs:code` no longer authors ADR or other general doc updates (MAR-65);
`/acs:docs-sync`'s doc-updater is the sole producer, and its `adr` doc area
writes the binding design's accepted decision records. Designer and reviewer
tasks both carry `adr_dir`.

All diagrams are Mermaid (an HLD excerpt may quote diagram lines); the
document references the HLD and LLD by path and never copies them wholesale.

## The constraints both roles carry

The designer and reviewer tasks both carry two declared constraints —
`required_sections` and `<constraint name="audience_style_profile">reviewers
(decision + trade-off narrative)</constraint>` — mirroring
`create-prd/SKILL.md`'s precedent.

`required_sections` is template-derived, NOT a hardcoded literal: the
coordinator RESOLVES the design template — the built-in `design-default`
(`${CLAUDE_PLUGIN_ROOT}/templates/design-default.md`), replaced by
`<checkout_root>/.acs/templates/design-default.md` when the repo has one — and
passes the section list DERIVED from that template file's `## ` headings
(there is no section-list setting) as the constraint on the designer and
reviewer tasks:
`<constraint name="required_sections">Decision &amp; options; HLD views affected; LLD; NFRs; Risks; Open questions</constraint>`
(the same six headings above, which the built-in template yields). A consumer
repo that supplies its own `<checkout_root>/.acs/templates/design-default.md`
has its `tech-design.md` gated against ITS sections. The
`audience_style_profile` constraint (MAR-150) is unchanged: the hand-off's
readers are reviewers weighing a decision.
