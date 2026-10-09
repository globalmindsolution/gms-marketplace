# /acs:create-prd — survey slices over disjoint repo areas

Open this when SKILL.md's Survey slices trigger holds: a brownfield or amend
survey whose code spans two or more disjoint top-level areas. Survey (what
"above" means here), Author ("below") and User interaction are SKILL.md's.

Slice the survey when the mode is brownfield or amend (you already know which
from Start: a located PRD means amend) AND the code the survey must cite spans
**two or more disjoint top-level areas** of the repo — top-level packages,
services, apps or plugins: the containers the architecture doc set names when
one exists, else the top-level directories of `git ls-files` that hold code.
Greenfield never slices (there is no code to survey; the elicitation plan is
one piece), and a repo whose code sits in one area runs the single surveyor
above.

**Partition rule.** Slice `lead` owns the repo root's files, the docs tree
(including an existing `<prd>` and `<roadmap>`) and the whole-product sections
of the notes: `## Mode & evidence`, the product-level `## PRD outline` (Vision,
Problem statement, personas, goals with their candidate metrics),
`## Roadmap outline`, `## Roadmap milestones`, `## Feature set` (a draft: the
`hub` author finalizes it) and `## Answer fidelity` — so each ledger id gets its
one line from one slice — plus the ADR-0012 doc-consistency step. Every other slice is one code area, named by its
directory basename (`api`, `web-app`, `billing`), and owns only
that area's paths: it records the features, product NFRs and code evidence its
area proves under `## PRD outline` and `## Code evidence`, candidate milestones
under `## Roadmap outline` (never `## Roadmap milestones`), and its area's
`## Open questions`, `## Risks` and `## Reviewer checklist` entries. An area is
a set of top-level directories and no directory belongs to two slices, so no
two slices survey — or cite — the same path.

1. Write `iter-1/surveyor-slices.json` (`acs.py write`), then spawn `lead` plus one surveyor
   per area in ONE message (at most `settings.parallel.max_agents`, waves beyond it), each `<task
   skill="create-prd" phase="surveyor" slice="<id>" …>` carrying
   `<constraint name="survey_area"><its top-level paths, or "lead"></constraint>`
   beside the survey constraints above.
2. Join the notes, `lead` first so the whole-product headings open the file:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
     --out <partition>/steps/create-prd/iter-1/authoring.md \
     <partition>/steps/create-prd/iter-1/authoring-lead.md \
     <partition>/steps/create-prd/iter-1/authoring-<area-1>.md …
   ```

3. Put the open questions of ALL slices to the user in ONE grouped
   clarification-ledger ask (User interaction) — never one ask per slice.
4. The `hub` author then runs exactly as below from the joined `iter-1/authoring.md`
   — and **synthesizes** it, because a mechanical join is not a synthesis:
   where two slices' notes contradict each other (one feature described two
   ways, an area's code evidence against a `lead` goal or constraint, a
   candidate milestone that fits no `lead` outline), it records the resolution
   with the evidence that settles it under a `## Synthesis` heading of
   `iter-1/authoring.md`, or returns `needs_input` with the contradiction as a
   question — never silently picks one side. It also reconciles
   `## Roadmap milestones` with the milestone headings it actually writes, and
   settles `## Feature set` from the features the area slices proved (one slug
   per feature, none twice); the feature authors are cut from that final list.
   No integration pass follows: the hub's index is the one seam.

A slice that returns `failed` or no usable `<result>` fails the survey: re-run
the failed slices once (together, in ONE message); still failing → fail the
run with the error recorded. The join never runs over a missing slice.
