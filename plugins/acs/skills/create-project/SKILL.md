---
name: create-project
description: Once dispatched it scaffolds a greenfield product's repository skeleton from the approved architecture doc set (or, when there is none, from a stack and layout the user confirms) — directory layout, build config, test framework with coverage tooling, linter/formatter, pre-commit, CI, and a minimal green vertical slice. Runs exactly once on a fresh product repo after /acs:create-architecture and before the first ticket; never on an existing codebase, which is the standardize-project leg's job.
when_to_use: Internal leg of /acs:project (bootstrap mode) — never the answer to a user request, even one that asks to scaffold a brand-new repo from its approved architecture. Route every such request to /acs:project, which detects greenfield vs existing from declared on-disk evidence and dispatches here itself with an explicit Skill call; do not invoke this leg directly.
argument-hint: "(no arguments)"
disallowed-tools: Edit, NotebookEdit
---

# /acs:create-project — coordinator instructions

You are the coordinator of /acs:create-project. You scaffold a fresh product's repo
skeleton from the approved architecture — or, when the repo has none, from a stack,
layout and coverage tooling the user confirms — so the ticket pipeline — especially the
/acs:code TDD gates — works from ticket #1. You orchestrate; subagents do the work.
This is a product-level skill with its own delivery ticket, branch, and PR; the
scaffolded CI workflow runs on that very PR. Greenfield only: existing codebases
never need this skill.

## Start

MANDATORY first action — locate the architecture doc set, before anything is
allocated. Documents are found, not configured: read CLAUDE.md and whatever docs
index it or the repo points at (e.g. `docs/README.md`), then Glob/Grep for
`hld/tech-stack.md`. Found → the directory holding it is `<architecture_dir>`, and
the scaffold is derived from it. None found (a directory without
`hld/tech-stack.md` does not count) → this is never a stop: the run takes the
**no-architecture fallback** (below) and works from the run's subject — what the
user asked for when invoking `/acs:project` or this leg, and the PRD if one is
found — and from the repo. Tell the user no architecture doc set was found and that
you will confirm the stack with them instead. Locate the PRD the same way (`<prd>`, a
secondary input; none found → leave it out of the scaffolder's inputs).

Then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-project --allocate
```

`--allocate` creates the delivery ticket (type `task`, title "Project scaffold",
e.g. `SHOP-3`), its workspace partition, the `.lock`, and an `in_progress` run
entry. Parse the printed context JSON; the fields you will use:

- `ticket_id`, `ticket`, `partition` — the delivery ticket and its workspace partition
- `checkout_root` — the consumer repo root (the only tree the scaffolder mutates)
- `settings` — `test_coverage_percent`, `formats`, `tracker`
- `models` — per-tier `{model, effort}` resolved from settings
- `reconcile`, `handoff_summary`, `prior_status`, `pipeline`

If `acs step start` exits non-zero: stop and surface its stderr verbatim — do not improvise.

Apply `context.models.<tier>.model` / `.effort` when spawning each subagent, unless
the value is `"inherit"`: the scaffolder (a `write` role) runs on the `executor` tier,
the build-checker (a `judge` role) on the `verifier` tier. If the runtime rejects the
model id or effort, FAIL the run with that exact error — no silent fallback.

## Resume & reconcile

`--allocate` always creates a fresh ticket, so `context.reconcile` is normally false.
Three cases:

- **Prior unfinished scaffold run.** Check `<workspace>/<repo_id>/tickets-index.json`
  for an earlier "Project scaffold" ticket that is not `done`. If one exists, resume
  it instead of scaffolding twice: (1) close the just-allocated ticket — write its
  `result.json` (see Finish) with `status: "failed"`, `summary: "duplicate
  allocation; resumed <PRIOR-ID>"`, and run the post-hook for it; (2) re-run
  `acs step start` with `--ticket <PRIOR-ID>` (no `--allocate`) and continue with that
  context — it will report `reconcile: true`.
- **`context.reconcile` is true** (resumed ticket): verify recorded progress against
  reality BEFORE continuing — re-read `steps/create-project/` artifacts,
  inspect `git -C <checkout_root> status` and `git log` on the scaffold branch, and
  re-run any build/lint/test command recorded as passing. Trust nothing you cannot
  re-verify; continue from the first unfinished phase.
- **`context.handoff_summary` exists**: read it, plus
  `steps/create-project/handoff-context.md` if present, do a light
  reconcile (spot-check its claims against the repo and partition), and continue
  from where it points.
- There is no plan artifact to reuse: a scaffolder report with no build-check ->
  build-check it; a build-check with findings and no later scaffolder report ->
  run the scaffolder with those findings as `<context>`. The scaffolder's
  iteration-1 authoring notes (`iter-1-authoring.md`) carry the file manifest,
  its Slices section and the commands every later iteration reads.
- **Slices (see Parallelism).** A resumed iteration re-runs only the slices whose
  report is missing: a scaffolder slice with no `iter-<n>/scaffolder-<id>.json`,
  a build-checker slice with no `iter-<n>/build-checker-<id>.md` — never a slice
  whose report exists; slice reports present but no
  `iter-<n>/scaffolder-integration.json` → run the integration pass before any
  build-check. Then re-join the build-checker slices with `acs.py notes
  merge` before judging the pass. Iteration 1 with `iter-1/authoring.md` written
  but no slice reports resumes at the build fan-out; the pin pass is not re-run.

## Greenfield gate

Start located the architecture doc set (`<architecture_dir>/hld/tech-stack.md`)
or chose the no-architecture fallback. Either way, YOU verify the repo is actually
greenfield before any planning:

```bash
git -C <checkout_root> ls-files | grep -vE '^(docs/|\.acs/|\.claude/|\.github/|\.gitignore$|README[^/]*$|LICENSE[^/]*$|CLAUDE\.md$)'
```

Any output (source trees, package manifests, lockfiles) means substantive
sources already exist. `.github/` is excluded because `/acs:setup` writes its CI
workflows (`acs-conventions.yml`, `acs-tests.yml`, `acs-e2e.yml`) onto a repo
with no source at all, and `/acs:project` (`acs_lib.project_mode`) deliberately
does not count them either — counting them here refused the very repo
`/acs:project` had just routed to this leg; `<architecture_dir>` and `<prd>` count as docs
even when they sit outside `docs/`. When resuming a prior scaffold ticket, run the
scan against the default branch instead (`git -C <checkout_root> ls-tree -r
--name-only origin/HEAD`) so the unfinished scaffold's own files do not trip it.

If substantive sources exist, REFUSE politely:

1. Tell the user /acs:create-project is greenfield-only and is never needed again
   once a codebase exists — point them at the pipeline instead: `/acs:create-ticket`
   then `/acs:ship` per change (and `/acs:create-architecture` re-runs keep the doc
   set current on an existing codebase).
2. Skip the reflection loop and go straight to Finish with `status: "failed"`,
   `summary: "greenfield-only: repository already contains substantive sources"`,
   all `states.scaffold` booleans `false`, and one blocking finding
   (`dimension: "greenfield"`) listing the files found.

## No-architecture fallback

Only when Start found no architecture doc set. Nothing refuses: the stack, the
layout and the coverage tooling that `hld/tech-stack.md` and the C4 views would have
pinned are confirmed with the user instead, BEFORE the scaffolder builds anything.

1. Draft a concrete proposal from the run's subject, the PRD (if found) and the repo
   (whatever docs, READMEs or notes it holds): the stack (languages, frameworks,
   package manager, test framework, linter/formatter, CI provider); the directory
   layout (the top-level components and where each lives); the coverage tooling and
   its threshold (`settings.test_coverage_percent`); and whether an e2e harness is
   wanted.
2. Run the clarification ledger (User interaction below): reuse any recorded answer,
   and ask everything still open in ONE grouped interaction — stack, layout and
   coverage tooling together, each with your proposal as the default option. Record
   each answer as its own `clarify.py add --skill create-project` entry before acting
   on it.
3. Spawn the scaffolder with those `C-n` entries in `<context>` in place of the
   `hld/` inputs, and `<constraint name="architecture_source">clarifications</constraint>`.
   Its authoring notes record that these clarification entries stand in for the
   architecture set and cite the `C-n` ids wherever they would cite `tech-stack.md`
   or the C4 views; the build-checker judges `tech-stack` and `layout` against those
   same entries.

If the user cannot be reached, the existing rule holds — never guess a stack: Finish
with `status: "interrupted"`, `stop_reason: "needs_input"` and the open questions. The completion report recommends
`/acs:create-architecture` so a doc set catches up with the scaffold; that
recommendation is advice, never a precondition.

## Reflection loop — scaffold -> build-check

The loop is scaffold -> build-check, at most 3 iterations, between two subagents:

- **scaffolder** — `acs:create-project-scaffolder`, a `write` role on the
  `executor` model tier. Iteration 1's scaffolder reads the architecture doc set (or,
  under the no-architecture fallback, the confirmed `C-n` entries), pins the
  scaffold — layout, package/build config, test and coverage tooling, lint, CI,
  the vertical slice, the exact verification commands, and the Slices section
  that partitions the file manifest — in its authoring notes (the **pin pass**,
  one un-sliced scaffolder). The build then fans out: one scaffolder per slice,
  in parallel, from iteration 1 (Parallelism below), each building its own files
  green, and an integration scaffolder reconciles the seams and makes the whole
  tree build green together before the build-check.
- **build-checker** — `acs:create-project-build-checker`, a `judge` role on the
  `verifier` model tier, read-only on the repo. It re-runs the notes' commands
  itself and judges the result fresh, as three dimension slices in parallel
  (Parallelism below).

On iterations 2-3 the build-checker's findings go verbatim into the next
scaffolder `<task>` `<context>` and the scaffolder authors the remediation
against the same iteration-1 notes — they are never re-authored, and no plan
phase sits in between. Decomposition is YOURS alone — subagents never spawn
subagents. Before the loop: `mkdir -p steps/create-project`.

**What an iteration counts:** one scaffold -> build-check round. create-project
has no path-driven check-depth selection: the cap is a fixed 3 in every
lane, and this ticket introduces none.

Messaging rules for every phase:

- Communicate per `the SubagentStop hook's message check`: you send a `<task>`
  whose `phase=` is the role (`scaffolder` or `build-checker`), the subagent
  returns a `<result>` with the same `phase=` as the final content of its reply.
  A sliced instance's `<task>` and `<result>` also carry `slice="<id>"`; the
  un-sliced pin pass omits it.
- Invalid message from a subagent: re-request once; still invalid -> fail the run,
  recording the validation error in result.json `errors`.
- Every phase's output is on disk before the next phase starts: the SubagentStop
  hook snapshots each `<result>` to `steps/create-project/iter-<n>/<phase>-message.xml`
  (a sliced instance's to `iter-<n>/<phase>-<slice>-message.xml`, so parallel
  instances never collide), and each agent writes its own report. The
  scaffolder's own artifacts are `iter-1-authoring.md` (authored once, by the
  iteration-1 pin pass: Analysis; File manifest; Slices; Commands; Vertical slice;
  Delivery; Risks; Build-checker checklist), the pin pass's `iter-1/scaffolder.json`
  each build slice's `iter-<n>/scaffolder-<slice>.json`, and the integration
  pass's `iter-<n>/scaffolder-integration.json`; the build-checker
  slices write `iter-<n>/build-checker-<slice>.md`, which you join into
  `iter-<n>/build-checker.md`. Every iteration's build-checker `<inputs>` name the
  iteration-1 notes.
- Spawn with the Agent tool, `subagent_type`
  `acs:create-project-scaffolder` / `acs:create-project-build-checker`; fall back to the
  un-namespaced name only if the runtime rejects the namespaced one.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

### Parallelism — scaffolder slices and build-checker slices

Every fan-out here is yours: spawn the N instances of the SAME agent in ONE
message (all foreground, all in the same message), wait for all of them, and
join their outputs before the next phase. At most `max_parallel = 4` instances
run per phase; beyond that, run the rest in waves of four.

**Scaffolder slices — the default, from iteration 1.** Iteration 1 is two steps.
First ONE un-sliced scaffolder runs the **pin pass**
(`<constraint name="pass">pin</constraint>`): it writes the authoring notes,
their Slices section included, and `iter-1/scaffolder.json`, and builds
nothing. Then the build fans out: one scaffolder per slice, spawned in ONE
message, each `<task skill="create-project" phase="scaffolder" slice="<id>" …>`
carrying `<constraint name="pass">build</constraint>` and
`<constraint name="files">` listing exactly the manifest files the notes' Slices
section assigns it. The partition rule is fixed:

| Slice | Owns | Its own check before it commits |
|---|---|---|
| `core` | the package/build manifest(s) and lockfile, the test framework and coverage config, the linter/formatter config, the directory layout, the entrypoint and its smoke test, and the e2e harness with its smoke e2e test when the notes pin one | the notes' install, build, lint and tests-with-coverage commands, all green |
| `ci` | the CI workflow file(s) | the workflow parses as YAML and runs the notes' Commands verbatim |
| `precommit` | the pre-commit config | `pre-commit validate-config` — never `pre-commit install`, whose hook would fire on the sibling slices' commits |
| `docs` | `README.md` and `.gitignore` | the README names the notes' real commands; `.gitignore` covers the stack's build outputs, dependency dirs and caches |

**What must stay in one slice:** everything the four commands need to go green
together — the manifests, the test/coverage and lint configs, the layout, the
entrypoint and smoke test, and the e2e harness — is ONE slice, `core`, because
none of those files can be proven green without the others, and `core` is the
only slice that installs dependencies or runs the four commands. A file two
concerns would share (e.g. a `pyproject.toml` holding build, lint and coverage
config) belongs to `core`. **The no-overlap guarantee:** the notes' Slices
section assigns every manifest file to exactly one slice id. Before spawning the
build, check that every manifest file appears in exactly one slice's list; a
file in none or in two sends the notes back to the pin pass (still iteration 1,
nothing built yet, so the notes are not frozen). A slice that owns no manifest
file is not spawned. The slices share the delivery branch you created: none
checks out or creates a branch; each stages only its own files (`git add --
<its files>`, never `git add -A`) and commits with the notes' commit message; on
git `index.lock` contention it waits briefly and retries the commit — it never
forces anything and never deletes the lock file.

**The integration pass — synthesis before the build-check.** A mechanical union
of slices is not a scaffold that builds: after ALL build slices have returned and
BEFORE the build-checker, spawn ONE more scaffolder with `slice="integration"`
and `<constraint name="pass">integration</constraint>`, whose `<inputs>` name the
notes and every slice's `iter-<n>/scaffolder-<slice>.json` and files. It
reconciles ONLY the seams between slices, never a slice's substance:

- **config files touched by more than one slice** — the CI workflow's commands
  and runtime versions against `core`'s manifest scripts and engines; the
  pre-commit hooks against `core`'s linter/formatter config and its pinned
  versions; `.gitignore` against `core`'s build outputs, coverage artefacts and
  dependency dirs;
- **the README** — its setup commands, layout and tooling sections against what
  `core`, `ci` and `precommit` actually wrote;
- **the whole tree green together** — it installs and runs the notes' four
  commands AND the pre-commit hooks (`pre-commit run --all-files`, never
  `pre-commit install`) on the combined tree, and fixes only what breaks at a
  seam.

It commits only the files it changed (`git add -- <those files>`, the same
`index.lock` retry rule) and writes `iter-<n>/scaffolder-integration.json`
listing each seam it changed: file, what, why, and which slices. A seam conflict
it cannot resolve from the notes and the evidence comes back as
`status="needs_input"` with a question (User interaction), never a guess. The
integration pass is skipped when only one scaffolder built (a single non-empty
slice). The build-checker judges the integrated result only after it returns.

On iterations 2-3 re-run only the slices that own a finding: route each finding
by its `file` through the notes' Slices section; a finding on a seam — a file
more than one slice's content depends on, the README, or a whole-tree command
failure (`build`, `lint`, `tests`, `coverage-tooling`, `vertical-slice`,
`pre-commit`) that no single slice's file explains — goes to the integration
pass; any other finding with no file goes to `core`. Every re-run scaffolder gets
ALL the build-checker's findings verbatim in its `<context>` — no plan phase in
between — and fixes the ones it owns. Whenever the run's build had more than one
slice, the integration pass runs again after that iteration's slices (alone, when
every finding is a seam's), before the build-checker.

**Build-checker slices — the default, every iteration.** The build-checker has
11 check dimensions, so it always runs as three slices, each a fresh instance of
`acs:create-project-build-checker` whose task carries `slice="<id>"` and
`<constraint name="dimensions">` naming the dimension numbers it owns:

| Slice | Dimensions | Owns the run of |
|---|---|---|
| `run` | 1 `build`, 2 `lint`, 3 `tests`, 4 `coverage-tooling`, 5 `vertical-slice`, 9 `pre-commit` | the ONE install/build/lint/test run, the pre-commit hooks on the tree, and the report's `## Verdict` block (the four `states.scaffold` booleans) |
| `structure` | 6 `layout`, 7 `tech-stack`, 11 `plan-conformance` | the layout and stack comparison against the architecture set (or the `C-n` entries) and the manifest, Slices and Delivery conformance |
| `wiring` | 8 `ci`, 10 `repo-hygiene` | the CI workflow read and the `git ls-files` hygiene scan |

The build/lint/test run stays in exactly one slice: `run` is the only slice that
executes the toolchain in the shared checkout, so two slices never install or
build at once, and pre-commit sits with it because its hooks run that same
toolchain on the same tree. Grounding policing applies in every slice. Spawn the
three slices in ONE message; each writes `iter-<n>/build-checker-<slice>.md`.
Join them, in the table's order, into the one report every later reader reads:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/create-project/iter-<n>/build-checker.md \
  <partition>/steps/create-project/iter-<n>/build-checker-run.md \
  <partition>/steps/create-project/iter-<n>/build-checker-structure.md \
  <partition>/steps/create-project/iter-<n>/build-checker-wiring.md
```

**De-duplicate after the join.** The slices own disjoint dimensions, so the
join is the synthesis — but two slices can still report one defect (a missing
`.gitignore` entry as both `repo-hygiene` and `plan-conformance`). Drop a finding
that cites the same location and the same defect as another slice's finding,
keeping the higher severity (here both block), and say so: append a
`## De-duplicated findings` section to the joined `iter-<n>/build-checker.md`
naming each dropped finding and the one kept.

**Pass rule for sliced judges:** the iteration passes only if EVERY slice
returned `status="completed"` with zero blocking findings (every finding blocks
here). Any slice's blocking finding blocks, and all slices' findings go verbatim
to the next scaffolders. A slice that failed or returned no usable result fails
the iteration — never "pass with a missing slice".

**Survey — not sliced.** The pin pass is the scaffolder's survey, but it decides
one coherent stack for a greenfield repo that has no top-level areas yet, so it
always runs as a single instance — there are no survey slices to synthesize.

### Scaffold — iteration 1 pins the scaffold before it builds

Spawn the pin-pass scaffolder (one instance, no `slice`). Build the input paths
from the `<architecture_dir>` and `<prd>` you located at Start (defaults shown);
put `settings.test_coverage_percent` in the constraints. Under the no-architecture
fallback the `hld/` inputs are absent and the `C-n` entries go in `<context>`
instead (see No-architecture fallback). Example (iteration 1, repo-relative input
paths):

```xml
<task skill="create-project" phase="scaffolder" ticket-id="SHOP-3" iteration="1">
  <objective>Pin the complete scaffold for this greenfield repo per the architecture doc set in the authoring notes steps/create-project/iter-1/authoring.md (list it in outputs), including the Slices section that assigns every manifest file to exactly one build slice. Build nothing: the build slices do that next.</objective>
  <inputs>
    <file>docs/architecture/hld/tech-stack.md</file>
    <file>docs/architecture/hld/c4-container.md</file>
    <file>docs/architecture/hld/c4-component.md</file>
    <file>docs/architecture/hld/overview.md</file>
    <file>docs/architecture/hld/deployment.md</file>
    <file>docs/product/prd.md</file>
  </inputs>
  <constraints>
    <constraint name="coverage_target">90</constraint>
    <constraint name="pass">pin</constraint>
    <constraint name="decisions">pin every choice in the notes before building; flag anything tech-stack.md leaves open as a needs_input question, do not guess</constraint>
  </constraints>
</task>
```

The notes MUST pin, concretely, with nothing left open, before any scaffolder builds:

- directory layout mirroring the C4 container/component views;
- package/build configuration files and the package manager;
- an e2e harness (e.g. Playwright for a web UI, an API-level suite for
  services) WHEN the architecture has a user-facing or cross-component
  surface — wired into CI plus one smoke e2e test in the vertical slice, and
  the matching `e2e` settings block proposed to the user (`command`, setup/
  teardown) for `.acs/settings.json`;
- the test framework AND coverage tooling, configured to fail below
  `settings.test_coverage_percent`;
- linter/formatter and pre-commit configuration;
- a CI workflow (e.g. `.github/workflows/ci.yml`) running build, lint, tests, and
  coverage;
- `.gitignore` and a README skeleton;
- the minimal GREEN vertical slice: one real entrypoint plus one smoke test that
  exercises it;
- the EXACT verification commands (install, build, lint, test-with-coverage) — the
  contract for both the build-checker and the CI workflow;
- the Slices section: every manifest file assigned to exactly one of `core`, `ci`,
  `precommit`, `docs` per the partition rule in Parallelism above.

If the pin pass returns `needs_input` with `<questions>` (a choice `tech-stack.md`
leaves open), resolve them in User interaction and re-run the pin pass for the same
iteration with the answers in `<context>`. Findings never return to a plan phase —
see Build-check below for where iteration 2+ findings go.

### Scaffold — the build

Iteration 1 only — create the delivery branch before any scaffolder runs (you own the
branch, the push and the PR; a scaffolder commits on the branch its notes name but
never pushes or opens the PR). Branch name per `settings.formats.branch_name`
(default `{type}/{ticket_id}-{slug}`) with `type=task`, the real ticket id, and the
slug of the ticket title:

```bash
git -C <checkout_root> checkout -b task/SHOP-3-project-scaffold
```

Spawn the build slices in ONE message, each with `<task skill="create-project"
phase="scaffolder" slice="<id>" ticket-id="..." iteration="n">` whose `<inputs>`
reference the iteration-1 authoring notes; on iterations 2-3 the build-checker's
findings go verbatim into each re-run scaffolder `<task>`'s `<context>`, with no
plan phase in between. `<constraint name="files">` pins the exact file set each
slice owns (from the notes' Slices section). Scaffolders mutate ONLY
`<checkout_root>`, and each only its own files. Iteration 1 runs the pin pass
alone, then every non-empty slice in parallel, then the integration pass;
iterations 2-3 re-run only the slices that own a finding, then the integration
pass (Parallelism above). A slice returning `needs_input` is resolved in User
interaction and that slice alone is re-run with the answers in `<context>`. The
build-checker runs only after ALL scaffolders, the integration pass last, finish
and judges the integrated result.

### Build-check

Spawn the three build-checker slices in ONE message, each with `<task
skill="create-project" phase="build-checker" slice="<id>" ...>` and its
`<constraint name="dimensions">` (Parallelism above), whose inputs are artifacts
only — the authoring notes, every `iter-<n>/scaffolder*.json` and the repo tree,
never scaffolder reasoning; each judges fresh. The build-checker MUST actually run, from `<checkout_root>`,
the exact commands the notes pinned, and see them pass — in the `run` slice, once:

1. dependency install — exit 0;
2. build — exit 0;
3. lint — exit 0;
4. tests with coverage — every test passes (the smoke test proves the vertical
   slice), the coverage tool reports a percentage, AND its config fails the run
   below `settings.test_coverage_percent`.

Plus static checks: layout matches the container/component views; the CI workflow
runs those same commands; `.gitignore` and README exist; the pre-commit config
installs and its hooks pass on the tree.

A scaffold that does not run green FAILS the build-check — every failing command is a
blocking finding. ALL findings block: zero findings = pass, in every slice (the
sliced-judge pass rule above). On findings (the slices have written
`iter-<n>/build-checker-<slice>.md` and you have joined them into
`iter-<n>/build-checker.md`), AUTOMATICALLY run the scaffolder again, passing every
finding of every slice to the next iteration's scaffolder `<task>` as `<context>`,
with no plan phase in between — the scaffolder authors the remediation. After iteration 3 with findings remaining: stop and go to Finish with
`status: "failed"` and the findings recorded.

## Delivery — commit, PR, CI proof

Only after a build-check pass (zero findings):

1. Commit on the scaffold branch, message per `settings.formats.commit_message`
   (default `{ticket_id} {summary}`), and push. `git add -A` is right here and
   only here: a scaffold is new files by definition, so there is no existing
   source for a broad add to sweep up (contrast /acs:standardize-project, which
   forbids the same command for exactly that reason):

```bash
git -C <checkout_root> add -A
git -C <checkout_root> commit -m "SHOP-3 Scaffold project skeleton per architecture doc set"
git -C <checkout_root> push -u origin task/SHOP-3-project-scaffold
```

2. **Open the PR** by following
   `${CLAUDE_PLUGIN_ROOT}/skills/create-prd/references/delivery-pr.md` — the label, the
   rendered title, the body template, the pre-open self-check, `gh pr create`,
   and recording `{number, url, branch}` as `states.pr`. Write the filled body
   to `steps/create-project/pr-body.md` and pass that path as
   `--body-file` to both the self-check and `gh pr create`; fill its
   placeholders from workspace state (ticket.json, the authoring notes,
   build-checker results). Read the number back with
   `gh pr view --json number,url,headRefName`.

3. CI proof — the scaffolded workflow runs on this very PR; green locally is not
   enough:

```bash
gh pr checks <number> --watch
```

   If CI fails: each failing check is a blocking finding. If the 3-iteration budget
   is not exhausted, run another scaffold -> build-check iteration to remediate
   (findings to the scaffolder's `<context>`; no plan phase), push to the same
   branch, and re-watch. Budget exhausted or still red: Finish with
   `status: "failed"`, findings recorded, and report the open PR.

Merging stays a user action: after their review the user runs
`/acs:merge-pr <ticket-id>`. Never invoke it yourself.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list --ticket <ticket-id>`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 clarifications are open, present them to the user in ONE grouped
interaction (e.g. a single AskUserQuestion containing all open questions as a
numbered list), not serial round-trips — one interaction per question wastes
user time. Record each answer as its own `clarify.py add` entry (one `C-<n>`
per question, `--source` preserved). Never skip a question, merge two questions
into one entry, or auto-answer a question outside the existing
`--source assumption --rationale "..."` rule.
Record every Q&A — obtained interactively or relayed in a /ship brief — with
`clarify.py add --skill create-project --question "..." --answer "..." --ticket <ticket-id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."` — assumptions surface
in the completion report's Findings and the PR body until a user confirms.
Before a needs_input handoff, record the outgoing questions as `open`
(`clarify.py add` without `--answer`).

Ask the user when genuinely ambiguous — e.g. `hld/tech-stack.md` names a language but
not the test framework, package manager, or CI provider; or the repo has no `origin`
remote to push to. Use AskUserQuestion (or plain questions) with concrete options and
fold the answers into the scaffolder's `<context>`. Do not re-ask anything the
architecture doc set already pins. With no architecture doc set, the stack, layout and
coverage tooling are always asked — once, grouped (see No-architecture fallback).

If you genuinely cannot reach the user (e.g. a non-interactive run): do NOT
guess. Run Finish with `status: "interrupted"`, `stop_reason: "needs_input"` and
the open questions in `summary`, and return a `<handoff skill="create-project" ticket-id="..."
status="needs_input">` carrying the `<questions>` as your final message.

## Context pressure

If your context runs low mid-run: flush in-flight work and soft context (user
answers, decisions, partial findings, gotchas, current iteration/phase) to
`steps/create-project/handoff-context.md`, then:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --ticket <ticket-id> --summary "done: <...>; in flight: <...>; next: <...>; decisions: <...>"
```

Tell the user the `continue_with` command it prints, then stop. handoff.py has
already finalized the step `interrupted` with `stop_reason: context_pressure`
(the summary recorded on the invocation as `handoff_summary`) and released the
lock — do NOT also write result.json or run the post-hook in this path.

## Finish

MANDATORY final step — never skipped, also on failure and on the greenfield refusal
(only the Context-pressure path above replaces it):

1. Write `steps/create-project/result.json`:

```json
{
  "status": "completed",
  "summary": "scaffold verified green locally and on the PR CI run",
  "states": {
    "scaffold": {"build": true, "lint": true, "tests": true, "coverage_tooling": true},
    "pr": {"number": 7, "url": "https://github.com/acme/shop/pull/7", "branch": "task/SHOP-3-project-scaffold"}
  },
  "findings": [],
  "errors": []
}
```

   - `status`: `completed | failed | interrupted` — nothing else is admitted.
     An `interrupted` result also carries `stop_reason`
     (`session_end | needs_input | context_pressure`).
   - `states.scaffold` keys are EXACTLY `build`, `lint`, `tests`, `coverage_tooling`
     — booleans reflecting what the BUILD-CHECKER (its `run` slice's `## Verdict`
     block in the joined report) or the PR's CI saw pass, not what the scaffolder
     claims. On failure keep whatever is true, e.g. build and lint green
     but tests red -> `{"build": true, "lint": true, "tests": false,
     "coverage_tooling": false}`.
   - `states.pr` (`number`, `url`, `branch`) only when a PR was opened.
   - `findings`: every open finding as
     `{"severity": "blocking|info", "dimension": "...", "detail": "..."}`.
   - There is no `handoff_summary` field here: `result.schema.json` refuses
     unknown keys. A context-pressure handoff never writes this file —
     `handoff.py` records its summary on the invocation.

2. Run the post-hook:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-project.py" --result-file "<the result.json you just wrote>"
```

   It finalizes the run entry, updates `run.json` and `tickets-index.json`,
   marks the delivery ticket `in_review` when a PR exists, and releases the
   lock.

3. Report a compact summary: ticket id, PR url, the four scaffold booleans, the
   wired commands (build / lint / test / coverage plus the threshold), and the next
   steps — review then `/acs:merge-pr <ticket-id>`, then `/acs:create-ticket` for
   the first real ticket (typically the MVP epic from the PRD roadmap). If you
   genuinely cannot reach the user (a non-interactive run): your final message is ONLY the `<handoff>` XML —
   status, summary under 1 KB, artifact refs (result.json, authoring notes, PR url),
   and `<next-step>`.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; under /acs:ship your final message is the `<handoff>` XML instead — this report is for direct invocations:

```markdown
## /acs:create-project · <ticket-id> · <status>

- **Ticket**: <id> — <title> (<type>)
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: scaffold summary — layout, build, test framework + coverage tooling, lint, CI, green vertical slice (build/lint/tests verified passing); delivery ticket id; PR number/URL
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, repo paths, branch, PR URL>
- **Metrics**: iterations <n>/<cap> · <wall time>
- **Next**: `/acs:merge-pr <ticket-id>` after reviewing the bootstrap PR (CI runs on it); then `/acs:create-ticket` for the MVP epic. When the run took the no-architecture fallback, also recommend `/acs:create-architecture` to document the confirmed stack and layout
```
