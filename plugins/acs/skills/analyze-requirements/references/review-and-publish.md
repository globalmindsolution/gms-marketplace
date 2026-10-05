# /acs:analyze-requirements — revising, reviewing and publishing the draft

Open this when a `draft` action carries `findings` (iteration ≥ 2), when the
`review` action is due, and when the `publish` action is due. The first
draft of a run needs only SKILL.md's Stage 3 and
`references/analysis-templates.md`.

**Where the cross-references below point.** "Two modes", "Stage 1",
"Stage 2", "Stage 3" and "The feature" are SKILL.md's sections.

## Revising the draft — iteration ≥ 2

On iteration ≥ 2 the action's `findings` are the previous iteration's
blocking findings, verbatim: put them ALL in the draft pass's `<context>`; it
fixes every one and nothing else in the seeded folder (deleting a context file
the analysis no longer has), recording them in `iter-<n>/authoring.md`.
A reviewer finding that is really a new question for the user — or a draft
pass that returns `needs_input` — goes through Stage 2 again (ledger first,
then one grouped ask) before the draft pass re-runs with the answers in
`<context>`: the controller blocks with `kind: "needs_input"` and hands you
`clarify` on the same iteration.

The working draft is a folder, `steps/analyze-requirements/iter-<n>/analysis/`
— the `draft` action prints it; when an iteration fails, the controller seeds
the next iteration's folder with a copy, so the draft is revised in place. The
published folder is a copy of those exact bytes (Publishing, below).

## The impact review

The `review` action. Spawn the three slices it prints (Judge slices, in
`references/fan-out.md`) in
ONE message, each with `<inputs>` of the draft folder (the action's `draft`,
and every file in its `draft_files`, README first), the authoring notes (the
action's `notes`), the analyst report (`analyst_report`), `requirements.md`
(its `## Refined` section as Stage 2 left it) and, on a ticket run, the ticket
file, the clarification ledger, `design.md` when it binds, and the repo paths
the impact maps name. Each judges fresh — never forward the
analyst's reasoning — and judges EVERY file plus the README's contexts table:
the `surface` slice re-derives the impact map from the codebase itself (and
whether the contexts split it honestly) and checks that every `## Questions for the user` item was
answered in the ledger or carried as an open/assumed entry, and that the
confirmed criteria match the refined requirements (and the ticket). Each writes
`steps/analyze-requirements/iter-<n>/impact-reviewer-<slice>.md`. Then
`record-review`: the controller joins the reports into
`iter-<n>/impact-reviewer.md` and derives the verdict from the slices'
`<result>` snapshots plus the draft's deterministic checks (below) — never
conclude a pass yourself.

## The deterministic checks

**The deterministic checks run beside the review.** `record-draft` runs the
$0 folder checks on the draft as it records it (`acs_lib.analysis_folder`) —
the same front-matter specs and section lists the `form` slice re-runs — so
they are done before the review spawns, not after it passes; the `review`
action lists their findings as `draft_checks`. Per file, they are:

```bash
# README.md
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/front_matter_check.py" \
  --require "ticket: str; ready_for_planning: bool; api_surface: bool; needs_design_recommendation: bool" \
  --ticket <id> "<draft>/README.md"
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/structure_lint.py" \
  --sections "Scope and summary; Contexts; Refined acceptance criteria; Cross-cutting risks and decisions; Questions and assumptions; Verdict" \
  --ordered "<draft>/README.md"

# every context file
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/front_matter_check.py" \
  --require "context: str" "<draft>/order-checkout.md"
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/structure_lint.py" \
  --sections "Impact map; Rules and edge cases; Risks; Open questions; API notes" \
  --ordered "<draft>/order-checkout.md"
```

and, across the folder: every file name is `README.md` or kebab-case `.md`
(no `index.md`, no subfolder), every `## Contexts` link resolves to a file in
the folder, every context file is linked, and `context` equals its file name.
(On a run with no ticket the README spec names `feature: str` in place of
`ticket: str` and takes no `--ticket`; a Discovery draft adds the version keys
to both specs, and `feature` to the context spec; `record-draft` picks the
specs from the run — you never choose them.)

`record-review` folds them into that iteration's blocking findings: a check
finding fails the iteration like a judge's blocking finding (it goes to the
next draft pass, or ends the run at the cap), never patched by you.

## Publishing

Once those pass, `publish` copies
every file of the draft folder byte-for-byte to the resolved analysis folder —
the feature's living analysis on a Discovery run,
`<development_dir>/<feature>/<ticket-id or run-id>/analysis/` on a shared
Development run, the run's state folder on a LOCAL one (recorded in
`publication`, never in `publication.files`) — removes a context file the new
analysis no longer has (only inside that folder), reads every file back, and
records the repo paths it wrote as `publication.files` in the loop,
repo-relative, with each file's sha. It never
stages, commits or pushes and refuses no branch (ADR-0127): the files are left
as uncommitted changes in the working tree, and `/acs:create-pr` reads those
recorded paths to make the documents commit, the first of the PR.
`record-publication` re-derives it from the working tree — every published
file is still the reviewed bytes — and completes the loop.

You never copy or commit the analysis yourself, and no subagent does: the
file-map write guard (`acs_lib/filemap.py`) denies any running `write`-kind
agent — the analyst included — a write under the run's document folders, because
these documents are precisely the control inputs an implementer is checked
against. The partition draft is workspace state and is never committed.

The front-matter check uses the same parser the gate and the
`api_surface_changed` predicate use, so a draft it accepts cannot be rejected
downstream for its front matter.

**The published file is the reusable record.** The run's
analysis folder is what `/acs:create-impl-plan`, `/acs:create-api-contract` and
`/acs:create-test-docs` read, and what the next run of this skill starts from
(Stage 1's reuse); the feature's living analysis is what the Design skills
(`/acs:create-architecture`, `/acs:create-data-design`, `/acs:create-flows`,
`/acs:create-design`) read and what every later Development run on the feature
starts from. Every reader opens the README first (`artifacts["analysis.md"]`)
and then only the context files it needs (`analysis_files`). The partition
copy exists only for the no-checkout case, where there is no docs folder to
publish to.
