# Writer slices — one contract-author per interface

Read this before the write, once the survey's Interface inventory is joined
and the grouped ask answered: it decides whether the writers run sliced, and
how a sliced run is spawned, integrated and joined.

When the change spans two or more interfaces, the contract-authors run in
parallel — that is the default, not an optimisation to reach for:

- **When.** The survey's inventory names two or more interfaces. Otherwise ONE
  contract-author, `slice="write"`, writes the whole change un-sliced: one
  writer has nothing disjoint to hand out and no seams.
- **The partition rule.** One slice owns one interface — its document under
  `lld/<feature>/api/` (only that slice edits it), the items it holds, and its
  own fragment of the run record — and the FIRST slice also owns the README
  files (`lld/<feature>/README.md`, `lld/README.md`). Every document is in
  exactly one slice and every item has exactly one owner: that is the
  guarantee two slices cannot overlap. Each task names its own interface
  document AND every other slice's in `<constraint name="slice_scope">`, so a
  slice knows what it must not touch.
- **Slice ids.** The interface slug (`customers`, `order-events`,
  `export-cli`) — `acs.py notes merge` reads a slice id as what follows the
  prefix its inputs share, so a hyphen is fine. `survey`, `write`,
  `integration` and `preamble` are reserved.
- **What a slice writes.** Its notes `iter-<n>/authoring-<k>.md`; its
  interface document in place, versioned through `acs.py design`; its fragment
  `steps/create-api-contract/api-contract-<k>.md` — the run record's five
  headings in order, no front matter and no title, only its own rows, revised
  in place across iterations; and its report `iter-<n>/contract-author-<k>.json`.
- **One message.** Spawn every slice of a wave in ONE message — one Agent call
  per slice, all in the same assistant message, in the foreground — then wait
  for ALL of them before anything else happens. At most
  `settings.parallel.max_agents` (default 4) slices per message; more
  interfaces run in waves of that size, the next wave spawned only once every
  slice of the previous one returned.
- **One working tree, no git writes.** Each slice writes ONLY its own files and
  lists them in its report's `files`; no slice stages, commits or touches a
  branch, so siblings never contend for the index. The join is the reports
  plus the baseline: a write outside a slice's scope is its defect, never a
  sibling's.
- **Questions and failures.** The `<questions>` of every slice that returned
  `needs_input` go to the user in ONE grouped ask; then only those slices
  re-run, under the same id, with the answers in `<context>`. A slice that
  `failed` is re-run alone once; still failed → the run fails. The join waits
  until every slice of the iteration has `completed`.
- **The integration pass — synthesis, before the join and before the
  reviewer.** A mechanical join is not a synthesis: slices that each wrote
  their own interface can disagree where the interfaces meet. Once every slice
  has completed, spawn ONE more contract-author with `slice="integration"`
  (the pattern `/acs:code-complex`'s final integration implementer uses). Its
  `<inputs>` name every slice's interface document, fragment, latest notes and
  latest report. It reconciles ONLY the seams between interfaces, and edits the
  documents and fragments in place to do it:
  - **error codes** — a code two interfaces return carries one meaning, one
    wording and one status in every document's `## Error model` table;
  - **shared definitions** — a type, enum, field name, identifier or error
    envelope two interfaces both use is spelled and shaped the same in every
    document;
  - **cross-references** — an item in one interface that names an item in
    another (an endpoint that emits an event, a command that calls an
    endpoint) names it exactly as the owning document's `### ` heading does;
  - **compatibility decisions** — two slices citing the same `C-n` state the
    same verdict and decision;
  - **scope and traceability hand-offs** — a surface one slice excluded as
    "another interface's" is specified by that interface (nothing dropped
    between slices), and an acceptance criterion one slice marks as a gap is
    not covered by another slice's item;
  - **indexes** — `lld/<feature>/README.md` lists every interface document.

  It never rewrites a slice's substance and never adds or removes an item —
  the derived `items` count stays true. Where the slices' notes contradict
  each other, it records the resolution with its evidence under a
  `## Synthesis` heading in its own notes, `iter-<n>/authoring-integration.md`,
  never silently picking one; a genuine conflict it cannot resolve from the
  evidence comes back as `status="needs_input"` with the question. It writes
  `iter-<n>/contract-author-integration.json` listing each seam it changed
  (file, what, why, which slices). The pass is skipped when the writer ran
  un-sliced — one writer has no seams — and, on iteration 2+, when there is
  nothing at a seam to reconcile (below).
- **The join — deterministic, never by hand.** Once the writers (and the
  integration pass, when it ran) completed:
  1. Join the writers' notes — each slice's LATEST notes (this iteration's
     when it ran, else those of the iteration it last ran), in slice order,
     and the integration pass's notes last when it ran:

     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
       --out <partition>/steps/create-api-contract/iter-<n>/writers.md \
       <partition>/steps/create-api-contract/iter-<n>/authoring-<k1>.md <…/authoring-<k2>.md> … \
       <partition>/steps/create-api-contract/iter-<n>/authoring-integration.md
     ```

  2. Write `steps/create-api-contract/api-contract-preamble.md`: the front
     matter and the `# API contract — <id>: <title>` line, nothing else, every
     value DERIVED — `ticket` is `<id>`, `items` the sum of the slices' latest
     reports' `items`, `interfaces` the union of their `interfaces`. It is the
     one draft file you write, and it holds no contract content.
  3. Join the draft, the preamble first and then every slice's fragment, in
     slice order:

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
  stay in the workspace), so the reviewer, the $0 checks and Publish all read
  ONE draft with each of the five headings once. A slice whose report
  miscounts its items is caught there: the reviewer's
  `versions-and-structure` dimension checks the derived `items` against the
  `### ` subsections.
- **Iteration 2+.** Group the findings by the slice that owns the document or
  item each one names, and re-run only those slices — each with EVERY finding
  verbatim in its `<context>`, fixing the ones in its own interface. A seam
  finding — one that spans two interfaces, or names an inconsistency between
  them — goes to the next iteration's integration pass, not to the slices. A
  slice not re-run keeps its document, fragment, notes and report as they
  are. The integration pass then runs again, with every finding in its
  `<context>` (alone, when only seam findings were open) — but only when a
  seam finding is open or a re-run slice's report lists a `seams` entry (its
  fix changed something another interface names). With neither, nothing at a
  seam has moved since the last integration pass, so skip it: the join uses
  that pass's latest notes, like any slice not re-run. Then the join follows.
