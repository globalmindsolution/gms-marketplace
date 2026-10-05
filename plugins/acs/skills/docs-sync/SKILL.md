---
name: docs-sync
description: Re-verify and complete the doc updates a ticket's changeset requires — independently re-derived from the working-tree changeset (acs.py changes diff), /code's result.json, and the final changeset review verdict, never from a hand-off summary alone. Leaves the doc changes uncommitted beside the code (no branch, no commit, no PR — /acs:create-pr commits them). Use whenever a change is done and the docs (README, API reference, configuration guide, runbook) must be brought in line with it — even a single stale value or sentence: a doc fix that follows from a ticket's change goes through this skill, not a direct edit. Call it as your first action on such a request — do not Glob, Grep, Read, ToolSearch or look for a shell or git first: it runs git itself and finds the changeset and docs.
when_to_use: Use when a ticket has a changeset in the working tree whose documentation still needs reconciling; workflows/ship.yaml places it after code and before create-pr, but it is runnable on its own whenever the docs have drifted from the diff.
argument-hint: "[ticket-id] [documents…] [prompt]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:docs-sync. Your job: independently re-derive
what documentation the ticket's changeset requires and write any missing or
incorrect doc updates into the SAME working tree `/acs:code` left its change
in — as uncommitted changes, never a branch, a commit or a PR (ADR-0127):
`/acs:create-pr` commits them as the ticket's doc-sync group. You orchestrate
two subagents over XML, each built for its half of the job: a **doc-updater**
that re-derives the doc delta from the changeset and writes the doc updates,
and a fresh **drift-reviewer** that re-derives the doc impact independently
and judges the changed docs (doc-updater → drift-reviewer). You never write
doc content yourself.

`/code`'s own step 4 no longer authors general doc updates — it only
reconciles factual claims in `docs/product/prd.md`/`docs/product/roadmap.md`
(MAR-65). This skill is now the sole producer of README/API/usage/
architecture/living-requirements/ADR doc updates for a ticket's changeset,
diff-grounded and best run once code (and the post-code test step) settle.

**What the pre-hook checks (and what it does not).**
`pre-docs-sync.py` checks only what re-running could not undo: settings
resolve, the run resolves to a live, unlocked partition. No ticket is required:
a run over a prompt or documents is synced the same way. It never refuses
— or warns — because an upstream artifact is missing, and it never refuses
because `/acs:code`, `/acs:review-code` or the post-code test steps have not
recorded a completed run: pipeline order lives in `workflows/ship.yaml`, not in
the gate, so docs-sync is an independent skill, runnable on its own against
whatever the working tree already holds. Run somewhere other than the run's cursor,
the pre-hook prints ONE advisory line on stderr (`acs: docs-sync normally
follows <predecessor> in ship.yaml; the cursor for <id> is <cursor>`) and lets
the skill run. The real precondition is a CHANGESET: with nothing changed since
the run's baseline there is nothing to re-derive — input 1 of "Inputs" below is
where you find that out, and "No doc impact" below is how you stop. Every other input below is read when present and
worked around when absent — the diff and the requirements are the fallback.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step docs-sync --args "$ARGUMENTS"
```

- If it exits non-zero: STOP and surface its stderr verbatim to the user. Do
  not improvise a workaround.
- Parse the printed context JSON. Fields you will use: `partition`,
  `requirements` (`{path, sources, acceptance_criteria, features, feature,
  needs_design}` — **Requirements: `context.requirements` / `acs.py
  requirements show` — a ticket id, documents and a prompt are only where they
  came from; never read ticket.json for acceptance criteria**), `ticket` and
  `ticket_id` (present only when a ticket is one of the sources), `settings`,
  `models`, `reconcile`, `handoff_summary`, `pipeline`, `post_hook`,
  `checkout_root`.

Throughout this file `<partition>` means the `partition` path from the
context JSON and `<id>` means `ticket_id` (e.g. `SHOP-123`) when the run has a
ticket, else `run_id`.

**No branch precondition.** docs-sync works in `<checkout_root>` on whatever
branch is checked out — it reads no recorded branch and refuses on none.
docs-sync NEVER creates a branch, NEVER switches one, NEVER stages or commits,
and NEVER opens a PR (ADR-0127); it adds its doc updates to the uncommitted
changeset `/acs:code` left in the working tree — same ticket, same future PR,
which `/acs:create-pr` opens.

## Resume & reconcile

- If `context.reconcile` is true (the step's
  previous invocation ended `interrupted` or `failed`; `context.prior_status`
  says which): verify recorded progress against reality
  BEFORE continuing — list `steps/docs-sync/iter-*/*-message.xml`,
  re-read `steps/docs-sync/state.json` if it exists, and check whether
  its `states.files` actually match the working tree
  (`acs.py changes diff --name-only`). Continue from the first unfinished phase/iteration; never redo
  work that demonstrably holds.
- If `context.handoff_summary` exists: read it plus
  `steps/docs-sync/handoff-context.md` (when present), do a
  light reconcile, and continue from where it points.
- Fresh run (`reconcile` false): start at iteration 1, doc-updater phase.
- There is no plan artifact to reuse: a doc-updater with no drift-reviewer →
  review it; a drift-reviewer with findings and no later doc-updater → the
  doc-updater with those findings as `<context>`. The doc-updater's authoring
  notes (`iter-<n>/authoring.md`) belong to their iteration.
- Both phases run sliced, so a phase can be half-done. A resumed iteration
  re-runs ONLY the slices whose report is missing: a doc area with no
  `iter-<n>/doc-updater-<area>.json` (check the working tree for its doc files
  first — a doc edit already on disk is kept, never redone), an integration pass that was
  due and has no `iter-<n>/doc-updater-integration.json` (run after the
  areas, as always), or a drift-review slice with
  no `iter-<n>/drift-reviewer-<slice>.md` — spawned together in one message.
  Then re-join with `acs.py notes merge` before moving on; a joined file with
  a slice report missing beside it is not a finished phase.

## Inputs — gather before the loop

The doc-updater's `<task>` `<inputs>` MUST literally enumerate, and the
doc-updater MUST read, exactly these artifacts — never a bare hand-off
summary. Inputs 3-6 are read when present; an absent one is named as absent
in the task and never stops the run (the diff and the requirements are the
subject docs-sync falls back to):

1. The ground-truth changeset, run from `<checkout_root>`:
   `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" changes diff --patch`
   — everything the ticket's run changed since its baseline, untracked files
   included. NEVER `git diff <default_branch>...HEAD`: it sees commits only,
   and the change is uncommitted until `/acs:create-pr`, so it is silently
   empty.
2. The requirements (title, description, acceptance criteria) —
   `requirements.path`, the run's `requirements.md` under `<partition>`,
   whatever container they came from (a ticket, a prompt, documents or a mix).
   With the run's `analysis.md` and the feature's living analysis
   (`feature_analysis`) when `acs.py artifacts show` reports them.
3. `steps/code/result.json`, specifically `states.docs_updated`
   (repo-relative paths of every doc file `/code` already changed).
4. The ticket's `steps/code/iter-<n>/implementer*.json` implementer
   report(s) (`execute*.json` on a run started before the rename),
   specifically the `problems` field.
5. The final review verdict, `steps/review-code/verdict.json` — the
   changeset review `/acs:review-code` recorded (`/acs:code` has no verifier
   of its own).
6. The ticket's binding design, when `context.design.required` is true
   (`context.design.source` is `own` for the ticket's own `needs_design`, or
   `parent` when it inherits its epic's design); absent otherwise. It is NOT
   under `<partition>` (that is the run directory, whose
   `steps/create-tech-design/tech-design.md` is only create-tech-design's
   unverified working draft). Resolve the published file with
   `acs.py artifacts show` — or `--ticket <parent-id>` when the
   source is `parent` — and read `artifacts["tech-design.md"]`: that is
   `acs_lib.artifacts.artifact_path`, which returns the first existing copy of
   the tech design in `<architecture_dir>/lld/<feature>/<that-id>/tech-design.md`
   (where `/acs:create-tech-design` publishes it), then a legacy `design.md`
   there or in `docs/tickets/<that-id>/` (read only), then the copy in that
   ticket's workspace partition (`context.design.dir`, used only when there was
   no checkout to publish into). On a ticketless run `design.dir` is null (or `design`
   is absent): read `artifacts["tech-design.md"]` from the run's own
   `artifacts show` when it reports one. `null` there means no design was published —
   name it absent. The same call reports `artifacts["api-contract.md"]`: read it
   and the `<architecture_dir>/lld/<feature>/api/` documents it links as the
   designed surface the repo's API reference and README must agree with.

`docs_updated`/`problems` may legitimately be near-empty for doc categories
`/code` no longer touches — reading them still tells docs-sync what `/code`'s
retained MAR-65 step 4 changed and any recorded doc-related friction
(including Boy-scout drift items carried verbatim from the implementation plan);
re-deriving from the live diff (input 1) remains docs-sync's own grounding
for every other doc category. Neither input substitutes for the other —
every phase (doc-updater and drift-reviewer alike) reads all six, independently.

**Constraints the task carries.** Every placeholder the doc-updater's and the
drift-reviewer's charters read comes from the `<task>`'s `<constraints>`, and only
names in the `constraintName` vocabulary of `the SubagentStop hook's message check`
validate — never invent a variant such as `commit_message_format` or
`contracts_root`. Pass, on every phase:

```xml
<constraints>
  <constraint name="partition">/abs/workspace/owner-repo/SHOP-123</constraint>
  <constraint name="checkout_root">/abs/path/to/the/checkout</constraint>
  <constraint name="requirements_dir">docs/requirements</constraint>
  <constraint name="functional_dir">docs/requirements/functional</constraint>
  <constraint name="non_functional_dir">docs/requirements/non-functional</constraint>
</constraints>
```

`checkout_root` is `context.checkout_root`; the requirements
trio is the requirements set and its functional and non-functional
subfolders. Add the other document locations the doc-updater's charter names —
`architecture_dir` and `adr_dir` — each as its own `<constraint>` under that
exact name.

Locate every one of them once, before the loop, the way any session finds a
document: CLAUDE.md and whatever docs index it or the repo points at (e.g.
`docs/README.md`), then a Glob/Grep by file name or content. Found → that
repo-relative location. Not found → the conventional default, where a doc
update would create it: `docs/requirements/` with `functional/` and
`non-functional/` subfolders (an existing set's own subfolder names are
followed), `docs/architecture/`, `docs/architecture/adr/`.

### No doc impact — finish without the loop

Take input 1 (`acs.py changes diff`) first. When it is **empty** — nothing
changed since the run's baseline — there is nothing to re-derive: spawn no
subagent, write nothing, and go straight to Finish with a completed result
that says so:

```json
{
  "status": "completed",
  "summary": "no changeset: acs.py changes diff is empty, so no doc is owed",
  "states": {"files": [], "review": {"iterations": 0, "findings_open": 0}},
  "findings": [],
  "errors": []
}
```

The same shape closes a run whose diff is non-empty but whose drift-reviewer
passes with the doc-updaters having written nothing (every doc the diff
touches is already correct): `files: []` on a `completed` result,
`review.iterations` counting the rounds that ran. An empty `files` is an
evidenced "no doc impact", never a failure — and never
an `outcome` value: this skill's fragment
(`skills/docs-sync/state.schema.json`) declares no outcome vocabulary, so the
result carries no `outcome` key at all.

## Reflection loop — doc-updater → drift-reviewer

The loop is doc-updater → drift-reviewer, max 3 iterations. Nothing plans
the doc updates ahead of the doc-updater — no planner, no plan phase — because
the doc-delta list is a derivation only the doc-updater uses: iteration 1's
doc-updater re-derives the doc impact from the six inputs, writes its
authoring notes (the doc-delta list, each item justified by the diff), and
writes the doc updates from them; the drift-reviewer re-derives the impact
itself and judges the result fresh. On iterations 2-3 the drift-reviewer's
findings go verbatim into the next doc-updater `<task>` `<context>` and the
doc-updater authors the remediation. Decomposition is YOURS alone —
subagents never spawn subagents. Both phases run as parallel slices of the
same agent file (Doc areas and Drift-review slices, below): spawn every
instance of a phase in ONE message, in the foreground, wait for all of them,
and join their outputs before the next phase starts. At most
`settings.parallel.max_agents` (default 4) instances per message; beyond it,
waves of that size. Both phases have at most four slices, so at the default
neither needs a second wave.

**What an iteration counts:** one doc-updater → drift-reviewer round.
docs-sync has no path-driven review-depth selection: the cap is a fixed 3 on
every run, and this ticket does not introduce one.

| Role | Agent | Kind | Spawn as | Writes |
|---|---|---|---|---|
| doc-updater | `acs:docs-sync-doc-updater` | write | `context.agents.doc-updater` | one instance per doc area: the doc files in its area its notes name (left uncommitted), `iter-<n>/authoring-<area>.md`, `iter-<n>/doc-updater-<area>.json` — you join the notes into `iter-<n>/authoring.md` |
| drift-reviewer | `acs:docs-sync-drift-reviewer` | judge | `context.agents.drift-reviewer` | one instance per dimension slice: `iter-<n>/drift-reviewer-<slice>.md` only — you join them into `iter-<n>/drift-reviewer.md` |

### Doc areas — the doc-updater partition

The doc delta splits into disjoint files by where each doc lives, so the
doc-updater runs **one instance per doc area, from iteration 1**. The areas
are fixed, and each is a slice id (`slice="<area>"`, carried with
`<constraint name="area">`):

| Area | Owns |
|---|---|
| `requirements` | every path under `requirements_dir` (functional and non-functional files and their `.evidence.md` sidecars) |
| `architecture` | every path under `architecture_dir` that is not under `adr_dir` (HLD, `lld/flows/`) |
| `adr` | every path under `adr_dir` |
| `general` | every other doc path: README, API/usage docs, and any doc outside the three directories |

**Partition rule.** A doc path belongs to the area whose directory is its
**longest matching prefix**, and to `general` when none matches — so an ADR
directory nested inside the architecture set is `adr`'s, never both. Every
path has exactly one owner, so two doc-updaters can never write the same
file. Each instance reads all six inputs and re-derives the doc impact from
the whole diff, but records and applies ONLY the doc-delta items whose target
file its area owns; an item it finds for another area it names under
"Out-of-area impact" in its notes, never edits. An area with no delta writes
notes saying so, with the Diff-analysis evidence, and writes no doc.
There is no separate survey role to slice: each area's doc-updater surveys
the diff itself, so the area split is the survey split too.

**One working tree, no git writes.** The doc-updaters write in the same
checkout, so each writes ONLY its own area's paths and lists every one in its
report's `files`; none stages, commits, stashes or touches a branch (ADR-0127),
so siblings never contend for the index. The join is the reports plus the
file-map guard; never revert or rewrite a sibling's file.

A doc-updater that returned `failed` or no usable `<result>` is re-requested
once; still failing, the run fails — the drift-reviewer never judges a
partial doc-updater phase.

**Integration pass — synthesis, not just a join.** Four areas written in
parallel can disagree where they meet, so after every area has returned and
BEFORE the drift-reviewer, spawn ONE more `acs:docs-sync-doc-updater` with
`slice="integration"` — the pattern `/acs:code-complex`'s final integration
implementer already uses. Its task names every area's
`iter-<n>/authoring-<area>.md` and `iter-<n>/doc-updater-<area>.json`. It
runs alone, after the areas, so its edits cannot race theirs. It reconciles
ONLY the seams:

- **docs index pages** — `docs/README.md` or whatever docs index the repo
  keeps, the requirements set's README/index, the architecture set's
  overview: every doc an area added, renamed or removed is listed (or
  delisted) there;
- **cross-links between areas** — an ADR ↔ the HLD section it changes, a
  requirement ↔ the architecture flow that realizes it, a README/API doc ↔
  the requirement or ADR it cites: every link resolves and both ends say the
  same thing; shared terms and IDs are spelled the same across areas;
- **each area's "Out-of-area impact" notes** — every out-of-area item must
  be applied by the owning area or explicitly resolved. The integration pass
  records each item's disposition: *applied by `<area>`* (citing that area's
  file), *applied here* (only when the item is itself a seam),
  or *not needed* (with the evidence). An item that is substance its owning
  area missed is not the integration pass's to write: it lists it as
  *unapplied → `<area>`*, you re-run that area's doc-updater once for the
  same iteration with the item in `<context>`, then re-run the integration
  pass; still unapplied, it goes to the drift-reviewer as-is.

It never rewrites an area's substance. Where two areas' notes contradict each
other, it records the resolution and its evidence under a `## Synthesis`
section of its notes, or returns `status="needs_input"` with a question —
never silently picks one. It writes only the seam files, lists them in
its report like the areas, commits nothing, and writes
`iter-<n>/authoring-integration.md` and `iter-<n>/doc-updater-integration.json`
listing each seam it changed (file, what, why, which areas). **Skipped when
only one area had changes** (at most one area's report lists a changed
doc, and no area recorded an out-of-area item): with a single writer there is
no seam.

**Join.** Then join the notes deterministically — never by merging prose
yourself — with the integration pass's notes last when it ran:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/docs-sync/iter-<n>/authoring.md \
  <partition>/steps/docs-sync/iter-<n>/authoring-requirements.md \
  <partition>/steps/docs-sync/iter-<n>/authoring-architecture.md \
  <partition>/steps/docs-sync/iter-<n>/authoring-adr.md \
  <partition>/steps/docs-sync/iter-<n>/authoring-general.md \
  <partition>/steps/docs-sync/iter-<n>/authoring-integration.md
```

`iter-<n>/authoring.md` is then the one set of notes the drift-reviewer
reads, each section once; the `iter-<n>/doc-updater-<slice>.json` reports stay
per slice, and Finish takes the union of their `files`.

**Iterations 2-3.** Re-spawn, in one message, one doc-updater per area that
owns the `file` of at least one finding; a finding with no `file`, or a file
no area claims, re-spawns every area. A **seam finding** — an index page
missing a doc, a cross-link between areas that is broken or contradicts, an
out-of-area item left without a disposition — goes to that iteration's
integration pass instead (or to the owning area, when the fix is that area's
substance), and the integration pass runs again whenever any area was
re-spawned or a seam finding is open. Every re-spawned doc-updater gets ALL
the findings verbatim in `<context>` and fixes only those in its own area. An
area not re-spawned keeps the notes of the iteration that last ran it, so
that iteration's join lists only the re-spawned slices' `authoring-<slice>.md`,
and the drift-reviewer's `<inputs>` name every iteration's joined
`authoring.md` so far.

### Drift-review slices

The drift-reviewer has six check dimensions, so it runs as three
**dimension slices** — fresh instances of the same agent file, spawned in one
message, each over a disjoint subset:

| Slice | Dimensions |
|---|---|
| `coverage` | 1 completeness · 6 authoring-conformance |
| `content` | 2 accuracy · 3 scope |
| `placement` | 4 mechanics · 5 requirements-routing |

Each task carries `slice="<id>"` and `<constraint name="dimensions">` listing
that row; every slice still re-derives the doc impact from the diff itself.
Join the reports with `acs.py notes merge --out
<partition>/steps/docs-sync/iter-<n>/drift-reviewer.md` over
`iter-<n>/drift-reviewer-coverage.md`, `iter-<n>/drift-reviewer-content.md`
and `iter-<n>/drift-reviewer-placement.md`.

**De-duplicate after the join.** The slices own disjoint dimensions, so the
merge is the synthesis — except that two slices can report one defect from
two angles. After the join, drop a finding that cites the same location (file
and line or section) and the same defect as another slice's finding, keeping
the one with the higher severity, and append a `## De-duplicated findings`
section to `iter-<n>/drift-reviewer.md` naming each dropped finding and the
one it duplicates. Only exact duplicates go: two defects at one location are
two findings.

**Pass rule.** The iteration passes only if EVERY slice returned
`status="completed"` with zero blocking findings. Any slice's blocking finding
blocks, and every slice's findings (after de-duplication) go verbatim to the next doc-updaters. A
slice that returned `status="failed"`, no usable `<result>`, or no report
file fails the iteration — never "pass with a missing slice".

For every phase:

1. Compose a `<task skill="docs-sync" phase="<role>" …>` per `the SubagentStop
   hook's message check` — `phase="doc-updater"` or `phase="drift-reviewer"`,
   the role's own name — with `<inputs>` listing the six artifacts above by
   path.
2. Validate EVERY message you send and receive — the SubagentStop hook checks each returned
   `<result>`'s `skill=`, `phase=` and `iteration=` (and `slice=` when sliced).

   On an invalid message from a subagent: re-request once with the
   validation error quoted; still invalid → fail the run, recording the
   error in `errors`.
3. Spawn the subagent with the Agent tool, `subagent_type` as below (fall
   back to the un-namespaced name — `docs-sync-doc-updater`,
   `docs-sync-drift-reviewer` — only if the runtime rejects the
   namespaced one). Spawn each role under the name in
   `context.agents.<role>` — the plugin's `acs:docs-sync-<role>`, or the generated
   `acs-docs-sync-<role>` copy `acs step start` wrote where `settings.models` sets
   a model or effort for it. Model and effort travel with that agent, so pass none
   of your own. If the runtime rejects the agent, FAIL the run with that exact
   error — no silent fallback.
4. Every phase output is persisted at the phase boundary, BEFORE the next
   phase starts: the SubagentStop hook snapshots each returned message to
   `steps/docs-sync/iter-<n>/<phase>-message.xml` — a sliced instance's at
   `iter-<n>/<phase>-<slice>-message.xml`, so parallel instances never
   collide; if that snapshot is
   missing (a host that does not fire the hook), write the `<task>` and
   `<result>` there yourself. The doc-updater's own artifacts are
   `iter-<n>/authoring.md` (Diff analysis; Doc-delta list; Cross-check
   against docs_updated/problems; Open questions) — written per area as
   `iter-<n>/authoring-<area>.md` and joined — and
   `iter-<n>/doc-updater.json` (per area, `iter-<n>/doc-updater-<area>.json`);
   the drift-reviewer's is `iter-<n>/drift-reviewer.md`, joined from
   `iter-<n>/drift-reviewer-<slice>.md` — never write a message over them.
   Every iteration's drift-reviewer `<inputs>` name that iteration's joined
   authoring notes and every area's doc-updater report.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

### Phase: doc-updater — `acs:docs-sync-doc-updater`

Objective, iteration 1: from the six inputs above, record the doc-delta
list in the authoring notes — which doc files need which specific changes
and why, each cross-referenced to the diff lines / `docs_updated` entries /
`problems` entries that justify it — and then apply those doc updates in the
working tree, left uncommitted beside the code change (never a branch, a
commit or a PR — `/acs:create-pr` commits them). Author the doc-delta report
using the FIXED v1 structure — the per-iteration role report every hooked
skill already writes (`iter-<n>/doc-updater.json` here, beside the
drift-reviewer's `iter-<n>/drift-reviewer.md`; every authoring skill's
writer keeps its `iter-<n>/authoring.md`). No new artifact type, no
settings-driven template, no new `settings.schema.json` keys.

Each instance's `<task>` carries `slice="<area>"` and
`<constraint name="area">` naming its area and the directories it owns, e.g.

```xml
<task skill="docs-sync" phase="doc-updater" slice="requirements" ticket-id="SHOP-123" iteration="1">
  <objective>Re-derive the doc impact of the changeset and apply only the doc-delta items under the requirements area.</objective>
  <inputs>…the six inputs…</inputs>
  <constraints>
    …the constraints above…
    <constraint name="area">requirements — owns every path under docs/requirements</constraint>
  </constraints>
</task>
```

If a doc-updater returns `needs_input` with `<questions>` (which of two
conflicting docs is authoritative, whether a doc edit is in scope), wait for
every area to return, then resolve ALL the areas' open questions in ONE
grouped ledger ask (User interaction) and re-run only the areas that asked,
in one message, for the same iteration with the answers in `<context>`.

### Phase: drift-reviewer — `acs:docs-sync-drift-reviewer`

Spawned fresh (sees artifacts, never the doc-updater's reasoning);
re-derives doc impact from the same six-input contract itself (not exempt
from the independent-re-derivation rule) and checks each doc
change is accurate, complete against the diff, and consistent with
`docs_updated` / `problems` / the final review verdict. It runs as the three
dimension slices above, all in one message, joined into
`iter-<n>/drift-reviewer.md`. ALL findings block;
zero findings = pass, across every slice. On findings: persist, then AUTOMATICALLY re-run the
doc-updater, passing every finding to the next iteration's doc-updater
`<task>` as `<context>`, with no plan phase in between — the doc-updater
authors the remediation, one instance per area the findings touch. After iteration 3 with findings remaining: stop,
final status `failed`.

**In a parallel group, the drift-reviewer judges the FINAL diff.** When
`/acs:ship` runs this step beside another member (the shipped workflow runs
it with `create-e2e-tests`), that sibling's writers write into the same
working tree while the doc-updaters work, so the doc-updaters may have derived
the delta from a changeset that was still growing. The drift-reviewer
re-derives from the changeset as it stands when it runs, so it is the check
that catches it — and it only can if it runs after every sibling writer has
written for the last time. `/acs:ship` holds this phase until then (its
"Running a parallel group"), and a sibling write that lands after a passing
drift review means one more drift review before Finish. A doc the sibling's
changes made stale is an ordinary finding for the next iteration's
doc-updater.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 clarifications are open, present them to the user in ONE grouped
interaction, not serial round-trips. Record each answer as its own
`clarify.py add` entry (one `C-<n>` per question, `--source` preserved).
Never skip a question, merge two questions into one entry, or auto-answer a
question outside the existing `--source assumption --rationale "..."` rule.
Record every Q&A with
`clarify.py add --skill docs-sync --question "..." --answer "..."`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."`. Before a needs_input
handoff, record the outgoing questions as `open` (`clarify.py add` without
`--answer`).

The doc-updater's own `<questions>` (uncertain whether a doc change is in
scope, or which of two conflicting docs is authoritative) go
through this same ledger-first path before the coordinator settles them and
carries the answer into the doc-updater `<task>` via `<context>`.

## Context pressure

If your context is running low mid-run: flush in-flight work and soft
context to `steps/docs-sync/handoff-context.md`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --summary "<done / in-flight / next / decisions>"
```

Tell the user the `continue_with` command it prints, and stop.

## Finish

MANDATORY final step — never skipped, including on failure or handoff:

1. Write `steps/docs-sync/result.json` per the result-document
   contract in INTERNALS.md. Canonical `states` keys (EXACT names) on
   success:

   ```json
   {
     "status": "completed",
     "summary": "drift-reviewer passed with zero findings on iteration 1",
     "states": {
       "files": ["docs/api/import.md", "README.md"],
       "review": {"iterations": 1, "findings_open": 0}
     },
     "findings": [],
     "errors": []
   }
   ```

   `files`: repo-relative paths of every doc file docs-sync itself changed and
   left uncommitted — the union over every doc area's (and the integration
   pass's) `iter-<n>/doc-updater-<area>.json` `files`, every iteration.
   `/acs:create-pr` commits them as the doc-sync group. `review`:
   `{iterations, findings_open}` — to which the post-hook's derivation may add
   `guard_denials` when the file-map guard denied a write during THIS run
   (the derivation reads `steps/<skill>/state.json` for every step,
   docs-sync's own included); never write that key yourself, and a run that
   tripped nothing carries no key at all. On `failed`: keep whatever is true,
   put the drift-reviewer's blocking findings in `findings`, and the reason in
   `summary`.

2. Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-docs-sync.py" --result-file "<the result.json you just wrote>"
   ```

   If it exits non-zero, surface its stderr verbatim — until it succeeds the
   run stays un-finalized in the ledger, so `acs.py run next` keeps
   offering docs-sync instead of moving on.

3. Report:
   - Direct invocation: a compact summary — the doc files written (left
     uncommitted in the working tree), iterations used, and the next step
     (`/acs:create-pr <id>`, which commits them).
   - Under /acs:ship: return ONLY the `<handoff>` XML as your final message —
     `status` matching result.json, `<summary>` <=1KB, `<artifacts>`
     referencing the changed doc paths, `<next-step>/acs:create-pr
     message.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your
final message is the `<handoff>` XML instead — this report is for direct
invocations:

```markdown
## /acs:docs-sync · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: doc files written (uncommitted); review iterations and open findings
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <uncommitted files written (repo-relative), partition files>
- **Metrics**: iterations <n>/<cap> · <wall time>
- **Next**: `/acs:create-pr <ticket-id>` — it commits the uncommitted files
```
