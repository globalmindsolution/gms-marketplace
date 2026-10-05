# Writer slices — one contract-author per contract-file group

Read this once `contracts_mode` is resolved, before the first spawn, whenever
`plan.md` exists and the repo keeps machine-readable contracts: it decides
whether the contract-authors run sliced, and how a sliced run is spawned,
integrated and joined.

When the contract splits into disjoint files, the contract-authors run in
parallel from iteration 1 — that is the default, not an optimisation to reach
for. Decide it once, after `contracts_mode` is resolved and before the first
spawn:

- **When.** `plan.md` exists, `contracts_mode` is a real `<contracts_dir>`, and
  the plan's file map (or its API/data-changes content) touches two or more
  contract-file groups. Otherwise — `no-machine-readable-contracts`, no plan,
  or a single group — ONE contract-author writes the whole draft, un-sliced:
  the contract is then a single document with nothing disjoint to hand out.
- **The partition rule.** A group is a set of machine-readable contract files
  under `<contracts_dir>` that describe one API: files that reference one
  another (a `$ref`, an `import`, an `include`) or that describe the same item
  are ONE group. Establish the groups by reading the files the plan names,
  never from their names; when you cannot establish them, do not slice. One
  slice owns one group — its contract files (only that slice edits
  them), the surface items those files describe, and its own fragment of the
  draft — and the FIRST slice also owns every item no contract file describes
  (a CLI flag, a library signature). Every contract file is in exactly one
  group and every item has exactly one owner: that is the guarantee two slices
  cannot overlap. Each task names its own group's files AND every other
  group's in `<constraint name="slice_scope">`, so a slice knows what it must
  not touch.
- **Slice ids.** The group's primary file stem, lowercase (`openapi`,
  `events`, `billing-api`) — `acs.py notes merge` reads a slice id as what
  follows the prefix its inputs share, so a hyphen is fine. `preamble` and
  `integration` are reserved.
- **What a slice writes.** Its notes `iter-<n>/authoring-<k>.md`; its fragment
  `steps/create-api-contract/api-contract-<k>.md` — the seven headings in
  order, no front matter and no title, only its own items, revised in place
  across iterations; its report `iter-<n>/contract-author-<k>.json`; and its
  group's contract files.
- **One message.** Spawn every slice of a wave in ONE message — one Agent call
  per slice, all in the same assistant message, in the foreground — then wait
  for ALL of them before anything else happens. At most
  `settings.parallel.max_agents` (default 4) slices per message; more groups
  run in waves of that size, the next wave spawned only once every slice of
  the previous one returned.
- **One working tree, no git writes.** Each slice writes ONLY its own group's
  files and lists them in its report's `contract_files`; no slice stages,
  commits or touches a branch, so siblings never contend for the index. The
  join is the reports plus the file-map guard: a write outside a slice's
  group is its defect, never a sibling's.
- **Questions and failures.** The `<questions>` of every slice that returned
  `needs_input` go to the user in ONE grouped ask (User interaction); then only
  those slices re-run, under the same id, with the answers in `<context>`. A
  slice that `failed` is re-run alone once; still failed → the run fails. The
  join waits until every slice of the iteration has `completed`.
- **The integration pass — synthesis, before the join and before the
  reviewer.** A mechanical join is not a synthesis: slices that each wrote
  their own group can disagree where the groups meet. Once every slice has
  completed, spawn ONE more contract-author with `slice="integration"` (the
  pattern `/acs:code-complex`'s final integration implementer uses). Its
  `<inputs>` name every slice's fragment, latest notes, latest report and
  contract files. It reconciles ONLY the seams between groups, and edits the
  fragments and contract files in place to do it:
  - **error codes** — a code two groups return carries one meaning, one
    wording and one status across every fragment's `## Error model` table;
  - **shared definitions** — a type, enum, field name or identifier two
    groups both use (a shared error body, a status enum, an id format) is
    spelled and shaped the same in every fragment and every contract file;
  - **cross-references** — an item in one group that names an item in
    another (an endpoint that emits a message, a command that prints a
    schema) names it exactly as the owning fragment's `### ` heading does;
  - **compatibility decisions** — two slices citing the same `C-n` state the
    same verdict and decision;
  - **scope and traceability hand-offs** — a surface one slice excluded as
    "another group's" is specified by that group (nothing dropped between
    slices), and an acceptance criterion one slice marks as a gap is not
    covered by another slice's item;
  - **indexes** — any index or README under `<contracts_dir>` that lists the
    contract files names every group's files.

  It never rewrites a slice's substance and never adds or removes an item —
  the derived `items` count stays true. Where the slices' notes contradict
  each other, it records the resolution with its evidence under a
  `## Synthesis` heading in its own notes, `iter-<n>/authoring-integration.md`,
  never silently picking one; a genuine conflict it cannot resolve from the
  evidence comes back as `status="needs_input"` with the question. It writes
  `iter-<n>/contract-author-integration.json` listing each seam it changed
  (file, what, why, which slices), and lists every contract file it touched in
  that report, leaving them uncommitted like every slice. The pass is
  skipped when the contract-author ran un-sliced — one writer has no seams —
  and, on iteration 2+, when there is nothing at a seam to reconcile (below).
- **The join — deterministic, never by hand.** Once the integration pass
  completed:
  1. Join the notes — each slice's LATEST notes (this iteration's when it ran,
     else those of the iteration it last ran), in slice order, and the
     integration pass's notes last:

     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
       --out <partition>/steps/create-api-contract/iter-<n>/authoring.md \
       <partition>/steps/create-api-contract/iter-<n>/authoring-<k1>.md <…/authoring-<k2>.md> … \
       <partition>/steps/create-api-contract/iter-<n>/authoring-integration.md
     ```

  2. Write `steps/create-api-contract/api-contract-preamble.md`: the front
     matter and the `# API contract — <id>: <title>` line, nothing else, every
     value DERIVED — `ticket` is `<id>`, `items` the sum of the slices' latest
     reports' `items`, `contract_files` the union of their `contract_files`.
     It is the one draft file you write, and it holds no contract content.
  3. Join the draft, the preamble first and then the fragments of every slice
     with `items` > 0, in slice order:

     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge --no-markers \
       --out <partition>/steps/create-api-contract/api-contract.md \
       <partition>/steps/create-api-contract/api-contract-preamble.md \
       <partition>/steps/create-api-contract/api-contract-<k1>.md <…/api-contract-<k2>.md> …
     ```

  The merge keeps the first input's preamble — the derived front matter — and
  lays each fragment's body under the one heading they share; `--no-markers`
  leaves out the `<!-- slice: … -->` lines, because this draft is what Publish
  copies into the repo (the notes and reviewer-report joins keep them — they
  stay in the workspace), so the
  contract-reviewer, the deterministic checks and Publish all read ONE draft
  with each of the seven headings once. A slice whose report miscounts its
  items is caught there: the reviewer's `front-matter` dimension checks the
  derived `items` against the `### ` subsections.
- **Iteration 2+.** Group the findings by the slice that owns the item or
  contract file each one names, and re-run only those slices — each with
  EVERY finding verbatim in its `<context>`, fixing the ones in its own group.
  A seam finding — one that spans two groups, or names an inconsistency
  between fragments — goes to the next iteration's integration pass, not to
  the slices. A slice not re-run keeps its fragment, notes and report as they
  are. The integration pass then runs again, with every finding in its
  `<context>` (alone, when only seam findings were open) — but only when a
  seam finding is open or a re-run slice's report lists a `seams` entry (its
  fix changed something another group names). With neither, nothing at a
  seam has moved since the last integration pass, so skip it: the join uses
  that pass's latest notes, like any slice not re-run. Then the join follows.
- **No surface.** Every slice reporting `items: 0` completes the run with
  `outcome: no_surface_owed`, exactly as un-sliced. A slice with `items: 0`
  writes no fragment and is left out of the draft join; its notes still join.
