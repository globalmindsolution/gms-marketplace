# /acs:analyze-requirements — the result document and the report

Read this at Finish: before you write `steps/analyze-requirements/result.json`
(the example is SKILL.md's), what each canonical `states` key means and
must equal, and what a failed run keeps; before you report a direct
invocation, what its summary covers.

## The `states` keys

Canonical `states` keys — EXACT names; `acs step finish` documents
them and the next steps read them:
- `ready_for_planning` (bool): the verdict. `false` is the `needs_input`
  arm, and `/acs:create-impl-plan` is what consumes it.
- `api_surface` (bool): whether the change adds or alters an API surface.
  It MUST equal the published front matter's `api_surface` (the README's) — that front
  matter is what `ship.yaml`'s `api_surface_changed` predicate and the
  `/acs:create-api-contract` gate actually read, and a result document that
  disagrees with it is a defect, not a second opinion.
- `questions_open` (int): clarifications still unanswered in the ledger —
  the count `clarify.py list --open` (`--ticket <id>` on a ticket run)
  prints after this run.
- `files` (array): every repo-relative path this run wrote and left
  uncommitted — the publish action's `publication.files` (every file of
  the published analysis folder, README first: the feature's living
  analysis on a Discovery run, e.g.
  `docs/product/features/wishlist/analysis/README.md`). `/acs:create-pr` commits
  them; empty when nothing was published or the analysis was kept local.

The needs_design recommendation is applied through its own CLI
(`acs.py requirements refine`), so it belongs in
`findings` and the completion report, not in `states`. On failure keep
whatever is true: `ready_for_planning: false`, the open findings in
`findings`, and the reason (`stalled`, the iteration cap, needs input) in
`summary` — the `failed` action's `stop_reason` and `reason`, verbatim.

## The direct-invocation summary

- Direct invocation: a compact summary — the verdict, the contexts it
  split the analysis into, the impact maps' component/file/test counts, what changed since the previous analysis
  when there was one, whether an API surface changes, the questions asked
  and answered (or "Stage 2 skipped"), the feature it is filed under, the
  criteria and needs_design confirmed into the requirements (and the
  ticket), any proposal still awaiting the user, open questions, where the
  analysis went ("shared to docs/development/…", "kept local (team
  default)", "kept local (this run only)"), the uncommitted files it left in
  the working tree, and the next step — on a
  Development run `/acs:create-impl-plan <id>` (`/acs:create-pr <id>` later
  commits everything the Development steps wrote); on a Discovery run the
  Design skills that read the feature's analysis (`/acs:create-design`,
  `/acs:create-data-design <feature>`, `/acs:create-flows <feature>`) or
  `/acs:create-ticket` to turn it into delivery work.
