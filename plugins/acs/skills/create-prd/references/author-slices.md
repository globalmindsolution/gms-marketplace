# /acs:create-prd — the author: the hub first, then one writer per feature

Open this at Author, every iteration. The document shapes are `documents.md`;
the slice ids, the cap and the plan file are `fan-out.md`. Author spawns are
`acs:create-prd-author` with `phase="author"` and a `slice`.

## The two kinds of author slice

| Slice | Owns (and writes nothing else) | Runs |
|---|---|---|
| `hub` | `<prd>`, `<roadmap>`, `iter-<n>/authoring.md` | first, alone |
| `feature-<slug>` | `<prd_dir>/features/<slug>/prd.md` and `steps/create-prd/features/<slug>/notes.md` | after `hub`, every one together in ONE message |

**Why this partition.** `prd.md` and `roadmap.md` are one coupled deliverable —
every roadmap milestone lists PRD features, every Must-have must land in a
milestone, a feature renamed in the hub is renamed in the roadmap, and amend
mode's diff discipline spans both — so the hub is ONE writer; nothing can own
half of it. The feature PRDs, by contrast, are disjoint files that each derive
from the hub's **Features (prioritized)** entry for their slug (title, MoSCoW
group, goals served), so they cannot be written until the hub has settled that
index, and once it has they cannot collide. The hub also owns the synthesis of a
sliced survey (`survey-slices.md`) and the notes' `## Feature set`: the final
list of slugs, titles, groups and goals the feature writers are cut from.

## The sequence, per iteration

1. **Hub.** Spawn one `hub` author with the notes, the answers and — from
   iteration 2 — the findings whose `file` is the hub, the roadmap or the notes.
   It writes `<prd>` and `<roadmap>`, finalizes `## Feature set` and completes
   the notes' lines that anchor in `prd.md` or `roadmap.md`, and reports in
   `iter-<n>/author-hub.json` the slugs whose documents must be (re)written:
   `features_to_write` — every feature on iteration 1; later, each one it added,
   renamed, re-prioritised or re-pointed at other goals, beside the ones the
   findings name. A feature the hub did not touch and no finding names is not
   re-run, and its document is not bumped.
2. **Plan the wave.** From `features_to_write` plus the features the findings
   name by `file`, write `iter-<n>/author-slices.json` (`acs.py write`):
   `{"feature-<slug>": ["<prd_dir>/features/<slug>/prd.md"], …}`.
3. **Features.** Spawn one `feature-<slug>` author per entry in ONE message
   (`settings.parallel.max_agents` per message, waves beyond it). Each task
   carries the notes, the answers, the hub's index entry for its slug
   (`<prd>` is an input) and the findings addressed to its file. A feature
   author writes only its own document and its notes
   (`steps/create-prd/features/<slug>/notes.md`, whole, every run): the
   `## Answer fidelity` lines for the answers that landed in its document, with
   verbatim anchors, and, from iteration 2, `## Findings addressed`.
4. **Wait for every slice** — a slice that returns `failed` or no usable
   `<result>` is re-run once, with the others untouched; still failing → the
   iteration fails with that error recorded. Then Versions (`versions.md`).

A `needs_input` from any slice is a product fact the answers do not settle: ask
the user (User interaction) and re-run only that slice.

## Findings go to the slice that owns the file

Route each finding verbatim to the `<context>` of the slice that owns its
`file`: a feature PRD → that feature's slice; the hub, the roadmap, a finding
about the feature set or one without a file → `hub`. A finding the hub's fix
turns into a change of the index is picked up by `features_to_write`.

## The notes and the floor

The notes stay ONE file per iteration, `iter-<n>/authoring.md`, owned by the
hub: the surveyor's lines naming a feature PRD as their target
(`- C-3 — features/wishlist/prd.md — …`) are placeholders the hub leaves
alone. The floor reads each feature's notes beside it (`--feature-notes`), and
a feature author's line for a ledger id wins over the placeholder, so a re-run
feature replaces only its own lines and nothing is joined by hand.

## Amend mode

`git diff` discipline spans the whole set (`git diff -- "<prd>" "<roadmap>"
"<prd_dir>/features"` plus `git status --short -- "<prd_dir>"` for the new
documents). A feature slice edits its existing document in place, preserving
untouched sections byte-for-byte; a new feature's slice creates its document.
