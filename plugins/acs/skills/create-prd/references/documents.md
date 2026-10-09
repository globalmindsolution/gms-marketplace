# /acs:create-prd — the PRD doc set (ADR-0142)

The PRD is a **hub plus one PRD per feature**, the layout product teams use to
keep a PRD reviewable as it grows: the hub holds what is true of the whole
product, each feature's document holds what is true of that feature, and ids
link the two. The author, the reviewer and the floor all work from this page.

```
<prd_dir>/                       (wherever the repo keeps its PRD, else docs/product/)
  prd.md                         the hub — the product PRD
  roadmap.md                     milestones → epics, release versions
  features/<slug>/prd.md         one PRD per feature (a Won't-have feature may have none)
  features/<slug>/analysis/      the feature's living analysis — /acs:analyze-requirements, never this skill
```

`<slug>` is the kebab-case feature slug the rest of acs already uses
(`lld/<slug>/`, a ticket's `features`), so one name reaches the feature's PRD,
analysis, LLD and tickets.

## The hub — `prd.md`

EXACTLY these eight sections, in this order, each non-empty (`required_sections`):
**Vision**, **Problem statement**, **Target users & personas**, **Goals &
success metrics**, **Features (prioritized)**, **Non-functional requirements**,
**Constraints & assumptions**, **Out of scope**. What changed from the single-file
PRD is only **Features (prioritized)** — it is the *index*:

- `### Must have`, `### Should have`, `### Could have`, `### Won't have` groups;
  every feature one top-level bullet, in exactly one group:

  ```
  - [Wishlist](features/wishlist/prd.md) — save products for later (supports G1, G3)
  ```

  The link is the feature's PRD; `(supports G<n>, …)` names the goal ids it
  serves, the ids defined in **Goals & success metrics** (`G1: …`). A
  Won't-have bullet may omit the link and carries its reason instead.
- A goal no feature serves gets an explicit deferral note in the index.
- The hub never restates a feature's requirements — it links them.
- **Non-functional requirements** are the product-wide ones; a feature's own
  performance or accessibility bar lives in that feature's PRD.

## A feature PRD — `features/<slug>/prd.md`

EXACTLY these sections, in this order, each non-empty (`feature_required_sections`);
the document opens at its `# <Feature name>` title:

| Section | Holds |
|---|---|
| **Summary** | what the feature is and the user problem it answers, in a paragraph |
| **Goals served** | the goal ids the hub's bullet names — the same set, each with how this feature moves its metric |
| **Requirements** | one line per requirement: `- **R1** — <the capability, observable and testable>`. Ids are `R<n>`, unique in the document, never reused or renumbered when one is cut (cite them as `<slug>/R1`) |
| **Acceptance criteria** | the feature-level done-when: concrete, testable statements (Given/When/Then or measurable thresholds) that trace to the requirement ids |
| **Dependencies** | other features (by slug), systems or decisions it needs; `None.` when there are none |
| **Out of scope** | what this feature deliberately does not do |

Priority is NOT a section: the hub's MoSCoW group is its one source, so the two
cannot drift. A feature-specific NFR is a requirement (`R<n>`) with a measurable
threshold.

## What the floor checks

`prd_feature_check.py` (rules in its docstring) holds the layout deterministically:
every Must/Should/Could bullet links a document, every link resolves, every
document is linked, the goal ids agree between the hub's bullet and the
feature's **Goals served** (and exist), the sections are present, in order and
non-empty, and the requirement ids are present and unique. Whether a requirement
is really testable, and an acceptance criterion really traces to it, is the
`substance` reviewer's judgement.

## Amend mode

The hub is edited in place, untouched sections byte-for-byte. A feature the
amendment does not touch keeps its document untouched (so its version is not
bumped). A new feature gets a new document. A **cut** feature moves to **Won't
have** keeping its link; nothing deletes a feature PRD — retiring it is
`/acs:set-doc-status deprecated`, a person's call.

## Versions

Every document of the set — the hub, the roadmap and each feature PRD — carries
the version front matter, set only by the coordinator through `acs.py design`
(see `versions.md`); an author never writes it.
