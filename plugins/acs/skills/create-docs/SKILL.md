---
name: create-docs
description: Bootstrap or maintain the product doc sets — quality (test strategy, coverage policy), operations (release process, runbooks, observability, incident response, test scheduling), principles (engineering principles + rationale) and standards (coding standards, conventions, review checklist) — from the plugin's templates, tailored to the PRD and the architecture set when present, each set delivered as its own docs-only PR on its own delivery ticket. Use for any request to write, refresh or finish any of those four sets or a document in them — a test strategy, a coverage policy, a runbook, a release process, an incident playbook, engineering principles or coding standards. Call it as your first action on such a request — do not Glob, Grep, Read or look for a shell first: it reads the PRD, architecture and existing sets itself.
when_to_use: Takes `all` or a comma-separated list of sets, runs the eligible ones in capped parallel, and resumes an interrupted set from its delivery-ticket id. Use when asked to create, bootstrap, generate, regenerate or maintain any of those doc sets; reads the architecture set when present (/acs:create-architecture is recommended first, never required).
argument-hint: "[all | <set>[,<set>...] | <delivery-ticket-id to resume>]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-docs, the product skill that bootstraps
or maintains the consumer's product doc sets — `quality`, `operations`,
`principles`, `standards` — in the consumer repo, each where the repo already
keeps it, else at its default location (`docs/quality/`, `docs/operations/`,
…), grounded in the PRD and the `architecture/` set when the repo has one, and shipped as a
docs-only PR on a fresh delivery ticket **per set**. This is a product-level
skill: it is ticket-independent until it mints its own delivery tickets. You
orchestrate subagents; you never write a doc file yourself.

One skill, four sets (ADR-0094). The sets used to be four internal leg skills
with a planner/executor/verifier trio each; they differed only in the row of
the table below, so that table is now the whole difference. The work is
**authoring** (ADR-0092 class D), so this skill owns exactly two subagents,
run as **one author/reviewer pair per doc set**: an **author** writes the set
from the templates and the upstream docs, with authoring notes, and a fresh
**reviewer** judges it against those notes. Nothing plans the set ahead of
the author — when the deliverable is a document bootstrapped from a
template, a plan to write it is a second copy of the writing.

Ground rules, non-negotiable:

- This is a hooked skill: `pre-create-docs.py` fires on the Skill call, and
  you look for the architecture doc set yourself at Start, once, for every set
  you go on to run — its absence is recorded, never a refusal; each set's own
  `acs step start --step create-docs --doc-set <set> --allocate` mints its
  delivery ticket, and each set's own `acs step finish` finalizes it.
  You never bypass, simulate, or duplicate a hook.
- You spawn `acs:create-docs-author` and `acs:create-docs-reviewer` — the
  same two agent files for every set; the set travels in the task's
  `<constraints>`. Decomposition is YOURS alone: subagents never spawn
  subagents.
- The sets are declared, not inferred: `acs_lib.DOC_SETS` is the one table
  that says what a set is (default location, delivery-ticket title, template
  directory, output files with their required sections, audience register,
  upstream inputs, dependency edges). Adding a fifth set is a row there plus
  its templates — never an edit to this prose.

## Argument — `<set|all>`, positional and comma-separated, or a ticket id

`/acs:create-docs <set>[,<set>...]`, `/acs:create-docs all`, or
`/acs:create-docs <delivery-ticket-id>`. A `<set>` is `quality`, `operations`,
`principles` or `standards`; the former leg name (`create-quality`) still
resolves to the same set for one release. `all` selects every declared set and
must be passed on its own — `all,quality` is refused, never guessed at. No
argument at all selects the declared default: every set.

You never parse this yourself. `acs_lib.parse_doc_set_arg` is the declared
parser and the Start snippet below calls it: it returns `candidates` (set
names, or `None` for "no argument"), `rejected`, `notices` — the exact
one-line messages to write to stderr, in order — and `resume`, the delivery
ticket id when the argument is exactly one. A token that **names no doc set**
is rejected and refuses the WHOLE run (exit 2, with a notice naming every
accepted spelling); the recognized remainder is never quietly fanned out
instead, and no rejected name is ever silently dropped.

`--for <set>[,<set>...]` stays accepted for **one release**. It parses to the
same set names and adds exactly one deprecated-form note on stderr saying the
positional form is the spelling now. Bare `--for`, with no names, selects
nothing: report the notice and stop.

## The two references, and when to open each

Nearly all of this skill is one flow: resolve the argument, mint a delivery
ticket per set, author it, ship it. Two parts are not, and each is read by
exactly one kind of run — so they live in references rather than inline:

| Open | When |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}/skills/create-docs/references/fan-out.md` | The eligible batch Start hands you holds MORE THAN ONE set. It defines **slice** and what `max_parallel` does with it, the worktree-per-set rule, and per-set failure isolation — so open it before the Reflection loop, which drives a slice. A single-set run and every resume run one set in the session checkout and skip it. |
| `${CLAUDE_PLUGIN_ROOT}/skills/create-docs/references/resume-and-handoff.md` | `context.reconcile` is true for a set, the argument was a delivery-ticket id, or your own context is running low. It carries the reconcile procedure and the handoff it reconciles against. A fresh run that finishes in one session skips it. |

## Start — locate the sets, then the argument, the table, and the eligible batch

MANDATORY first action — locate the documents this run reads and writes. No
setting says where they live: find them the way any session does — CLAUDE.md
(project instructions, loaded in every session) and whatever docs index it or
the repo points at (e.g. `docs/README.md`), then a Glob/Grep search by file
name from the checkout root (see Checkout root, below). Record each location
repo-relative:

- **The architecture set** — the directory holding `hld/tech-stack.md`; a
  directory without that file is not the set. None found → do NOT stop:
  record `architecture_dir` as absent for every set this run starts, tell the
  user once "no architecture doc set found (expected hld/tech-stack.md) —
  architecture-derived tailoring falls back to the repo/PRD; run
  /acs:create-architecture first for stack-grounded docs" (a recommendation,
  never a precondition), and go on. Looked for here once for the whole run.
- **The PRD** — the product `prd.md` (conventionally `docs/product/prd.md`).
- **Each declared set** — present when its sentinel file (the first file in
  its row of the table under "The doc sets") exists; record the directory
  holding it, or that the set is absent. A set's **location** is where you
  found it, else its default location (`default_dirs` in the Start output).

Then resolve settings, the argument, the doc-set table and the eligible
batch, passing the present set names comma-separated (empty when none):

```bash
python3 - "$ARGUMENTS" "<comma-separated present sets>" <<'PY'
import json, os, sys
sys.path.insert(0, os.path.join(os.environ["CLAUDE_PLUGIN_ROOT"], "hooks", "scripts"))
import acs_lib as lib
cwd = os.getcwd()
args_text = sys.argv[1] if len(sys.argv) > 1 else ""
present = [s for s in (sys.argv[2] if len(sys.argv) > 2 else "").split(",") if s]
settings, _sources = lib.load_settings(cwd)
try:
    workspace = lib.validate_settings(settings, cwd)
except lib.GateError as exc:
    sys.stderr.write("acs create-docs: %s\n" % exc)
    sys.exit(2)
root = lib.checkout_root(cwd) or cwd
repo_id = lib.repo_partition_id(cwd)
tickets_index = lib.read_json(lib.index_path(workspace, repo_id)) or {}
request = lib.parse_doc_set_arg(args_text)
for note in request.notices:
    sys.stderr.write(note + "\n")
if request.rejected or request.candidates == []:
    sys.exit(2)
max_parallel = 2  # this skill's own cap; ship.yaml carries no max_parallel (ADR-0096)
batches = ([] if request.resume else
           lib.fanout_batches(tickets_index, candidates=request.candidates, present=present))
print(json.dumps({"workspace": workspace, "repo_id": repo_id, "checkout_root": root,
                  "requested": request.candidates, "rejected": request.rejected,
                  "notices": request.notices, "resume": request.resume,
                  "max_parallel": max_parallel, "batches": batches,
                  "doc_sets": lib.DOC_SETS,
                  "default_dirs": lib.DOC_SET_DEFAULT_DIR}, indent=2))
PY
```

**Exit 2.** When `lib.validate_settings` raises `GateError`, the snippet
writes the error to stderr and exits 2: surface stderr verbatim and stop —
a hand-set setting is malformed or this is not a git checkout. A repo with no
settings file resolves on the defaults.

**`resume` set** → skip eligibility entirely and go to "Per-set Start", resume
form, for that one ticket.

**Eligibility.** `acs_lib.fanout_batches(tickets_index, candidates, present)`
is the **declared, not inferred** eligibility predicate, and `present` is
what you found at Start: a set is eligible only when it is not already in the
repo (not in `present` — its sentinel was not found), it has no open
(non-`done`) delivery ticket already in flight, and every **hard** dependency
is present. A **soft** dependency (today, exactly `standards` → `principles`)
never makes a set ineligible on its own — it only keeps the two out of the
**same batch**, so `principles` lands in an earlier batch than `standards` on
the default request. Do not reorder, re-derive or hard-code the batches you
are handed. A named but ineligible set is reported with its reason (already
in the repo / already in flight / blocked by a hard dependency the repo does
not have yet), never silently dropped. If the eligible batch is empty: report
why, per candidate, and stop.

**Checkout root.** The Start search runs from the checkout root (`git
rev-parse --show-toplevel`, the Start output's `checkout_root`), never a
subdirectory, so a run started from a repo subdirectory (or from a set's own
worktree on resume) does not read an already-shipped doc set as absent.
`fanout_batches` reads no disk itself: `present` is all it knows of the repo.

## The doc sets

`doc_sets` in the Start output is `acs_lib.DOC_SETS`, the single declaration.
For reading, the rows are:

| Set | Default location | Files (first = sentinel) | Audience |
|-----|------------------|--------------------------|----------|
| `quality` | `docs/quality` | `test-strategy.md`, `coverage-policy.md` | QA (test/verification runbook register) |
| `operations` | `docs/operations` | `release-process.md`, `runbooks.md`, `observability.md`, `incident-response.md`, `test-scheduling.md` | ops/SRE (runbook register) |
| `principles` | `docs/principles` | `principles.md` | engineers (concise normative rules) |
| `standards` | `docs/standards` | `coding-standards.md`, `conventions.md`, `review-checklist.md` | engineers (concise normative rules) |

Each file's required sections are `doc_sets[<set>].files[<file>]`; each set's
template directory is `${CLAUDE_PLUGIN_ROOT}/templates/<doc_sets[<set>].template_dir>/`;
its upstream inputs are `doc_sets[<set>].upstream` (see Inputs & mode). You
copy these into task constraints; you never restate them from memory.

## Per-set Start — sequential, one delivery ticket per set

For every set in the current slice, in the order `fanout_batches` handed them
to you, run its Start **sequentially** — never concurrently, and never from
inside a spawned subagent:

- Fresh run (the normal case; each set gets its own delivery ticket):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-docs --doc-set <set> --allocate
```

- Resume (`resume` from Start, or a `continue_with` command from a handoff):
  do NOT allocate — rejoin that partition; the set is `ticket.doc_set`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-docs --ticket <delivery-ticket-id>
```

If `acs step start` exits non-zero: STOP and surface its stderr verbatim to the
user — never improvise a substitute. One specific case: on a
fresh/unreconciled workspace partition, `--allocate` refuses with exit 2 and
a ranked local-evidence reconciliation proposal (`allocate_ticket_id`'s
fail-closed gate, MAR-402) instead of minting the delivery ticket. Relay that
stderr verbatim, obtain the confirmed start number from the user — never
invent it — and re-run that set's Start with `--seed-next <n>` added. Every
set allocates from the same `(repo_id, prefix)` partition, and Starts run
sequentially, so once one set's `--seed-next` succeeds the remaining sets'
Starts proceed normally.

Otherwise parse the printed context JSON; the fields you need: `partition`,
`ticket_id`, `ticket` (its `doc_set` names the set; its title is
`doc_sets[<set>].title`), `settings` (`formats`, `tracker`), `models`,
`reconcile`, `handoff_summary`, `post_hook`, `pipeline`, `checkout_root`. The
delivery ticket is type `task`; `acs step start` has already created the
partition, ticket.json, the lock, the session pointer, and the `in_progress`
run entry. If `settings.tracker.provider` is `github` or `jira`, sync the
ticket out via `gh`/`acli` per the tracker config.

**Where `acs step start` runs.** Every step through a set's Start runs from
the **session checkout** (`cwd` unchanged), never from its worktree: running
it from the worktree would resolve a different `checkout_id` than the one the
pre-hook's `PreToolUse(Skill)` envelope recorded its gate evidence under, and
report the run's enforcement as unconfirmed. The session pointer is therefore
shared between the slice's sets — display-level only; every downstream
consumer is given the ticket id explicitly.

## Inputs & mode

The upstream inputs are declared per set in `doc_sets[<set>].upstream`:

- `prd`: the PRD you located at Start — the named slice (`quality` and
  `operations` read its Non-functional requirements section specifically;
  `principles` and `standards` read the PRD generally).
- `architecture`: the full architecture set you located at Start — upstream
  of every set **when the repo has one**. **Graceful degradation
  (mandatory):** when no architecture set exists, you omit the
  `architecture_dir` constraint and add `architecture-optional`; the author
  authors the set from the PRD when one exists, else from the repo itself
  (build manifests, CI config, source layout) and the run's subject, records
  "no architecture set: architecture-derived tailoring falls back to the
  repo/PRD" in its authoring notes, and routes every product fact it would
  have taken from the architecture set (stack, deployment target, CI system,
  components) through the clarification ledger for the user to confirm —
  never a block, never a guess.
- `principles`: `true` for `standards` only — read the `principles/` set
  **when a `principles/` doc set actually exists at the principles set's
  location**. The conformance chain is `architecture → principles →
  standards`, an altitude gradient where an abstract principle is realized by
  a concrete standard. **Graceful degradation (mandatory):** when no
  principles set exists there yet, the author notes this explicitly and
  PROCEEDS — grounding N/A for the run, never a block. `principles` itself
  has NO cross-read on `standards/` or any downstream set.

**There is no per-set opt-out, and no missing upstream doc refuses a
run.** A set is skipped only for a reason Start reports (already in the
repo, already in flight, a missing hard dependency). A repo with no
architecture set never stops any set, and a repo with no principles set
never stops a `standards` run.

Mode is a two-way split, keyed to the set's own location only:

- **bootstrap** — no doc set exists yet at the location.
- **re-run/amend** — the set exists — regenerate/tailor in place, preserving
  still-accurate content.

The author decides the mode from the disk and records it; you do not
pre-decide it.

## Output contract

For each set, the author writes EXACTLY the files `doc_sets[<set>].files`
lists, bootstrapped from `templates/<template_dir>/` into
`<checkout_root>/<location>/` (no other repo file is touched). It bootstraps
each file from its template verbatim, then lightly tailors it to the consumer's
detected stack (read from the `architecture/` set, else from the repo and the
user-confirmed ledger answers) and, for `standards`, to
the stated principles when available — the same bootstrap-then-tailor shape
`/acs:create-project` uses for its scaffold templates. Living parts (a
coverage ledger, a postmortem log) are explicitly out of scope: these files
document strategy, policy, principles and standards, not a running log.

## Reflection loop — author → review, one pair per set

The loop per set is author → review, max 3 iterations. **What an iteration
counts:** one author → review round. Nothing plans the set ahead of the
author: iteration 1's author reads the upstream inputs, decides the mode,
authors the set, and writes its authoring notes; the reviewer judges the
result fresh. On iterations 2-3 the reviewer's findings go verbatim into the
next author `<task>` `<context>` and the author writes the remediation. This
skill has no path-driven review-depth selection: the cap is a fixed 3 for
every set.

| Role | Agent | Kind | Spawn as | Writes |
|---|---|---|---|---|
| author | `acs:create-docs-author` | write | `context.agents.author` | the set's `output-files` under its location, `iter-<n>/authoring.md`, `iter-<n>/author.json` |
| reviewer | `acs:create-docs-reviewer` | judge | `context.agents.reviewer` | `iter-<n>/reviewer-<slice>.md` only, one per dimension slice — you join them into `iter-<n>/reviewer.md` |

Drive this slice's sets together from this coordinator, in parallel phase
batches — the mechanism `/acs:code`'s coordinator already uses to run several
implementers whose file maps are disjoint (`code/SKILL.md`), reused, never a
new one. Every fan-out is yours: spawn every instance of a phase in ONE
message, in the foreground, wait for all of them, and join their outputs
before the next phase starts.

### Author

Spawn this slice's authors (`acs:create-docs-author`, one per set, at
most `max_parallel`) in ONE message. Every author writes in its own set's
worktree on the branch that set's Branch step created, to that set's own
location — disjoint by construction. Iteration 1 authors; iteration 2+
remediates the findings in `<context>`.

**Partition rule — one writer per set, never finer.** A writer owns exactly
one set: its `output-files` under its own location, in its own worktree, on
its own branch. Two sets never share a location (`DOC_SETS` gives each its
own default directory, and a set found in the repo is found by its own
sentinel file), so two authors cannot write the same file. A set is NOT split
further into per-file authors: its mode, its authoring notes, its Upstream
inventory and its consistency findings span the whole set, and the
`max_parallel` cap is already spent on sets. Nor is there a survey role to
slice: each author surveys its own set's upstream inputs, so the survey
already runs one per set.

**No integration pass — the sets are fully independent.** Parallel writers
elsewhere are followed by an integration pass that reconciles the seams
between their files; here there is no seam to reconcile. Each set is its own
delivery ticket, branch, worktree, PR and review, and no set's files link
into another set written in the same batch: the one cross-set read
(`standards` grounding on `principles`) is a soft dependency that
`fanout_batches` keeps out of the same batch, so `principles` is already on
disk when `standards` is authored. Doc-graph drift between a set and its
upstream docs is the author's ADR-0012 consistency step and the reviewer's
`consistency` dimension, per set.

### Review

After the slice's authors return, spawn this slice's reviewers — for every
set, one `acs:create-docs-reviewer` per **dimension slice** below, every
reviewer of every set in one message. A *dimension slice* (the task's
`slice=` attribute) is a disjoint subset of the reviewer's eight check
dimensions, each run by a fresh instance of the same reviewer agent file —
not to be confused with the *set slice* `max_parallel` caps
(`references/fan-out.md`):

| Dimension slice | Dimensions | Deterministic checker it owns |
|---|---|---|
| `files` | 1 doc-set-completeness · 3 required-sections · 5 docs-only-changeset · 7 structure | `structure_lint.py` |
| `content` | 2 architecture-conformance · 4 authoring-conformance · 6 consistency · 8 audience-style | `citation_check.py` |

Two dimension slices per set against at most `max_parallel` = 2 sets keeps
every Review message at **at most 4 reviewer instances**, the per-phase
fan-out cap. Each reviewer's `<task>` carries `slice="<id>"` and
`<constraint name="dimensions">` listing its dimension numbers and names from
this table; it runs only those (grounding is policed in every slice), writes
`iter-<n>/reviewer-<slice>.md`, and returns a `<result … slice="<id>">`. When
every dimension slice of a set has returned, join that set's reports
deterministically — never by merging prose yourself:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" notes merge \
  --out <partition>/steps/create-docs/iter-<n>/reviewer.md \
  <partition>/steps/create-docs/iter-<n>/reviewer-files.md \
  <partition>/steps/create-docs/iter-<n>/reviewer-content.md
```

`iter-<n>/reviewer.md` is then the one review report the next author, the
resume reconcile and the result document read, each section once.

**De-duplicate after the join.** The dimension slices own disjoint
dimensions, so the merge is the synthesis — except that two slices can report
one defect from two angles (a missing section is both `required-sections`
and `structure`). After the join, drop a finding that cites the same
location (file and section or line) and the same defect as another slice's
finding, keeping the one with the higher severity, and append a
`## De-duplicated findings` section to `iter-<n>/reviewer.md` naming each
dropped finding and the one it duplicates. Only exact duplicates go: two
defects at one location are two findings.

**Pass rule (per set, all dimension slices).** A set's iteration passes only
when EVERY one of its dimension slices returned `status="completed"` with
zero blocking findings (the waived `audience-style` register, `severity="info"`,
does not block). Any slice's blocking finding blocks the set, and every
slice's findings (after de-duplication) go verbatim to that set's next author. A dimension slice
that returned `status="failed"`, no usable `<result>`, or no report file
fails the iteration — never "pass with a missing slice".

The reviewer judges fresh from artifacts only (never the author's reasoning) and
checks, all blocking: every planned file exists and no unplanned extra
file; the tailored content conforms to the architecture set (when absent: to
the repo evidence and the ledger-confirmed facts the notes cite); required
sections are present in each file (`required_sections:<file>`);
the authoring notes were followed, including independent corroboration of
every upstream-fact citation in the Upstream inventory; the changeset is docs-only;
any consistency finding the author surfaced was resolved or explicitly
user-deferred in the clarification ledger; the deterministic structure floor;
and the audience register (`audience_style_profile`). Zero findings = pass —
proceed to Delivery. On findings, they go verbatim into the next iteration's
author `<task>` `<context>` and the run continues author → review. After
iteration 3 with findings remaining: stop that set, final status `failed`,
findings recorded in its result document; commit whatever was written to its
local ticket branch so nothing is lost, but do NOT push or open the PR.

The reviewer task's `<constraints>` also carry `prd`, `architecture_dir`
(or `architecture-optional` when the repo has no architecture set),
`principles_dir` when applicable, each file's `required_sections:<file>`
and the `audience_style_profile` — exactly the author task's constraints,
so the two phases judge the same contract.

### Messages

Spawn subagents with the Agent tool: subagent_type `acs:create-docs-author`
/ `acs:create-docs-reviewer` (fall back to the un-namespaced name —
`create-docs-author` / `create-docs-reviewer` — if the runtime rejects the
namespaced one). Spawn each role under the name in
`context.agents.<role>` — the plugin's `acs:create-docs-<role>`, or the generated
`acs-create-docs-<role>` copy `acs step start` wrote where `settings.models` sets a
model or effort for it. Model and effort travel with that agent, so pass none of
your own. If the runtime rejects the agent, FAIL that set's run with that exact
error — no silent fallback.

**Spawn in the foreground and wait on the result, never on a clock.** Pass
`run_in_background: false` to the Agent tool: the phase's `<result>` is your
next input and nothing else can usefully happen while it runs. If the
runtime moves the agent to the background anyway, wait for its completion
notification — never poll with `sleep` loops (`for i in $(seq 1 40); do
sleep 15; done` and its kin), which wait a fixed ten minutes whatever the
agent did and spent a whole 1800s setup on the 2026-09-15 release gate.

Communicate in XML per `the SubagentStop hook's message check`. The phase is
the role: `phase="author"` or `phase="reviewer"`. The set rides in the
constraints; compose them from `doc_sets[<set>]` and the locations you
recorded at Start (`doc_set_path` is the set's own location), never from
memory. Example author task for `quality`:

```xml
<task skill="create-docs" phase="author" ticket-id="SHOP-2" iteration="1">
  <objective>Author the quality/ doc set: read the PRD's Non-functional requirements and the architecture set, decide bootstrap vs re-run from the disk, bootstrap each file from its template and tailor it to the detected stack, and record the authoring notes.</objective>
  <inputs>
    <file>docs/product/prd.md</file>
    <file>docs/architecture/</file>
    <file>docs/quality/</file>
  </inputs>
  <constraints>
    <constraint name="partition">/abs/workspace/owner-repo/SHOP-2</constraint>
    <constraint name="doc_set">quality</constraint>
    <constraint name="doc_set_path">docs/quality</constraint>
    <constraint name="template_dir">quality</constraint>
    <constraint name="output-files">test-strategy.md, coverage-policy.md only — no other file</constraint>
    <constraint name="required_sections:test-strategy.md">Testing philosophy; Coverage policy; Suite inventory; CI gates; Flaky-test policy</constraint>
    <constraint name="required_sections:coverage-policy.md">Target and hard-fail rule; Exclusions; Measurement per stack; Escalation</constraint>
    <constraint name="audience_style_profile">QA (test/verification runbook register)</constraint>
    <constraint name="prd">docs/product/prd.md</constraint>
    <constraint name="prd_slice">Non-functional requirements</constraint>
    <constraint name="architecture_dir">docs/architecture</constraint>
  </constraints>
</task>
```

For `standards`, add `<constraint name="principles_dir">docs/principles</constraint>`
naming the principles set's location (the author and reviewer check the
set exists on disk themselves), and
`<constraint name="principles-optional">the principles/ set may be absent — treat as grounding N/A for this iteration, never a block.</constraint>`.
With no architecture set, drop `architecture_dir` and the architecture
`<inputs>` entry and add
`<constraint name="architecture-optional">no architecture set: architecture-derived tailoring falls back to the repo/PRD; confirm every such product fact through the clarification ledger.</constraint>`.
The reviewer task carries the same constraints, and its `<inputs>` name the
authoring notes and author report of the iteration under review. Each
reviewer task is one dimension slice: `slice=` on the `<task>` and a
`dimensions` constraint, e.g.

```xml
<task skill="create-docs" phase="reviewer" slice="files" ticket-id="SHOP-2" iteration="1">
  <objective>Review the quality/ doc set on dimensions 1, 3, 5 and 7 only.</objective>
  <inputs>…the author task's inputs, plus iter-1/authoring.md and iter-1/author.json…</inputs>
  <constraints>
    …the author task's constraints, verbatim…
    <constraint name="dimensions">1 doc-set-completeness; 3 required-sections; 5 docs-only-changeset; 7 structure</constraint>
  </constraints>
</task>
```

On iteration 2+ every dimension slice's `<context>` carries ALL the prior
iteration's findings (the joined `iter-<n-1>/reviewer.md`); each slice
confirms the ones in its own dimensions are fixed.

Validate EVERY message you send and receive, for every set — the SubagentStop hook checks each returned
`<result>`'s `skill=`, `phase=` and `iteration=` (and `slice=` when sliced).

On an invalid message, re-request it once (for a reviewer, only that
dimension slice); if still invalid, fail **that
set's** run with the validation error recorded in its own `errors` — never
another set's.

Every phase output is persisted at the phase boundary, BEFORE the next phase
starts: the SubagentStop hook snapshots each returned message to
`steps/create-docs/iter-<n>/<phase>-message.xml` — a dimension-sliced
reviewer's at `iter-<n>/reviewer-<slice>-message.xml`, so the slices never
collide; if that snapshot is missing
(a host that does not fire the hook), write the `<task>` and `<result>` there
yourself. The author's own artifacts are `iter-<n>/authoring.md` (Mode;
Upstream inventory with cited, verbatim-excerpted facts; Consistency
findings; Decisions) and `iter-<n>/author.json`; each reviewer slice's is
`iter-<n>/reviewer-<slice>.md`, joined into `iter-<n>/reviewer.md` — never
write a message over them. Every iteration's
reviewer `<inputs>` name that iteration's authoring notes.

## User interaction

**Clarification ledger first.** Before asking the user anything, run
`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/clarify.py" list --ticket <ticket-id>`
and reuse any recorded answer — re-asking an answered question is a defect.
When ≥2 clarifications are open, present them to the user in ONE grouped
interaction (a single AskUserQuestion containing all open questions as a
numbered list), not serial round-trips. Record each answer as its own
`clarify.py add` entry (one `C-<n>` per question, `--source` preserved).
Never skip a question, merge two questions into one entry, or auto-answer a
question outside the existing `--source assumption --rationale "..."` rule.
Record every Q&A — obtained interactively or relayed in a brief — with
`clarify.py add --skill create-docs --question "..." --answer "..." --ticket <ticket-id>`
BEFORE acting on it, and pass the relevant `C-n` entries to subagents in
`<context>`. If the user is unavailable or says "you decide": record the
decision with `--source assumption --rationale "..."` — assumptions surface
in the completion report's Findings and the PR body until a user confirms.
Before a needs_input handoff, record the outgoing questions as `open`
(`clarify.py add` without `--answer`).

The author's consistency findings (the ADR-0012 design-time
doc-consistency step: gaps and staleness across the doc graph, recorded in
its authoring notes, or returned as `<questions>` on `needs_input` when one
blocks authoring) go through this same ledger-first path: the user decides
which adjustments to apply, the next author iteration applies them, and the
reviewer confirms each was resolved or deferred. Ask when genuinely ambiguous
— at minimum, any gap between the PRD and the architecture set, every
architecture-derived product fact the author could not ground when the repo
has no architecture set (and, for
`standards`, the principles set) the author surfaces. Do not ask about
things those docs already answer.

If you genuinely cannot reach the user (a non-interactive run), do not guess
— run Finish with `status: "interrupted"` and `stop_reason: "needs_input"`,
then return a `<handoff skill="create-docs" ticket-id="<id>" status="needs_input">`
with the `<questions>` list instead.

## Delivery (branch, commit, PR) — per set, one independent PR each

The delivery-ticket pattern, done by you, inside that set's worktree
(/acs:create-design and /acs:code are not involved):

1. **Branch** (before the first author writes): require a clean working
   tree (`git status --porcelain` empty — if not, ask the user before
   proceeding). Render `settings.formats.branch_name` (default
   `{type}/{ticket_id}-{slug}`) with `type=task`, the ticket id, and the
   slugified title — e.g. `task/SHOP-2-product-quality-doc-set` — and
   `git checkout -b` it from the default branch.
2. **Commit** (after the reviewer passes): stage ONLY `<location>/` and verify
   the diff is docs-only (`git diff --cached --name-only` — every path under
   the set's location). Commit with `settings.formats.commit_message` (default
   `{ticket_id} {summary}`), e.g. `SHOP-2 Add product quality doc set` (or
   `Regenerate …` on re-run).
3. **Push & PR**: `git push -u origin <branch>`, then follow
   `${CLAUDE_PLUGIN_ROOT}/skills/create-prd/references/delivery-pr.md` — the label,
   the rendered title, the body template, the pre-open self-check, `gh pr
   create`, and recording `{number, url, branch}` for the result document.

Run those three steps once **per set**, in that set's own worktree. The result
is one independent delivery ticket and one independent docs-only PR **per set**
— never one shared branch, never a combined PR.

## Finish — per set

MANDATORY final step for every set started — never skipped, also on failure:

1. Write `steps/create-docs/result.json` per the
   result-document contract in INTERNALS.md. Canonical `states` keys (exact
   names): `doc_set` and `pr`. `path` is the set's location; `files` entries
   are paths relative to it:

```json
{
  "status": "completed",
  "summary": "quality doc set reviewed against the architecture set; docs-only PR opened",
  "states": {
    "doc_set": {
      "set": "quality",
      "path": "docs/quality",
      "files": ["test-strategy.md", "coverage-policy.md"]
    },
    "pr": {"number": 8, "url": "https://github.com/owner/repo/pull/8", "branch": "task/SHOP-2-product-quality-doc-set"}
  },
  "findings": [],
  "errors": []
}
```

   On failure: `status: "failed"`, the blocking findings in `findings`, the
   reason in `summary`, keep whatever is true in `states` (e.g. the
   written `doc_set` files without `pr`). On
   handoff you write no result document: the handoff in
   `references/resume-and-handoff.md` runs `handoff.py`, which finalizes the step `interrupted` with
   `stop_reason: context_pressure` and records its summary on the invocation.
   (`handed_off` is not a status and `handoff_summary` is not a result field.)

2. Run, from the session checkout:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-docs.py" --result-file "<the result.json you just wrote>"
```

   It finalizes that set's run entry, its own `run.json` (`flow:
   "product"`, step `create-docs`) and its `tickets-index.json` entry, and
   moves the delivery ticket to `in_review` when a PR was recorded — exactly
   once per set.

3. Remove each set's worktree once its Delivery is done (`git worktree
   remove <path>`); a failed set keeps its worktree and branch so a resume
   finds them.

## Completion report (normative)

Every terminal outcome of a direct invocation ends your final message with
the standard block (INTERNALS.md "Completion report"), rendered per set — one
line for each set this run attempted — only AFTER every started set's
post-hook succeeded. Same labels, same order, `none` where empty:

```markdown
## /acs:create-docs · <status>

- **Requested**: <the sets you were asked for, "default (all declared)", or the resumed ticket id>
- **Batch**: <eligible sets this pass, in slices of <max_parallel>, or "none — see reasons">
- **<set>**: <ticket-id> — <status> — <PR url, or reason>
- **Findings**: <open findings / clarifications / ineligible sets with reasons, or "none">
- **Metrics**: per set — iterations <n>/<cap> · <wall time>
- **Next**: `/acs:merge-pr <ticket-id>` per completed set after reviewing its docs PR; `/acs:create-docs <ticket-id>` for any set that did not complete
```
