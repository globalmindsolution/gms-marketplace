# Workspace & State Management

## Two stores: the repo's phase folders and the workspace

A run's files live in two places, split by audience, and every requirement
below belongs to exactly one of them
([ADR-0128](../../architecture/adr/0128-requirements-from-any-container.md)):

| | Repo phase folders | Workspace |
|---|----------------|---------------------|
| **Where** | one folder per phase, keyed by the run's feature: Discovery `<prd_dir>/features/<feature>/`, Design `<architecture_dir>/lld/<feature>/<ticket-id or run-id>/`, Development `<development_dir>/<feature>/<ticket-id or run-id>/` | `<workspace>/<repo>/` — the ticket partition `<ticket-id>/` and the run partition `runs/<run-id>/` |
| **Holds** | the human-facing documents: the feature's living analysis, an `analysis/` folder (Discovery, [ADR-0133](../../architecture/adr/0133-analysis-is-a-folder-by-bounded-context.md)); `tech-design.md` (a legacy `design.md` still read, [ADR-0135](../../architecture/adr/0135-create-tech-design.md)), `api-contract.md` (Design); a Development run's `analysis/` folder, `plan.md`, `test-cases.md` (Development) | the ticket (`ticket.json`) and its clarification ledger; the run ledger: `run.json`, `requirements.md`, `subject/` (`sources.json` and the copied documents), `steps/<skill>/state.json`, each step's `result.json` and `iter-<n>/` audit trail, verdicts, `lock.json`, `lock-events.jsonl`, a ticketless run's `clarifications.json`, `agents/`, and the repo-level `tickets-index.json` / `runs-index.json` / `counters.json` / `sessions/` |
| **Versioned** | yes — written uncommitted by the skills, committed by `/create-pr` (ADR-0127), reviewed in the PR | no — gitignored |
| **Written by** | the coordinators of the skills that own each document | hooks and the `acs.py` CLIs; the skills' coordinators and subagents through `acs.py write`, never the `Write` tool |

`<prd_dir>` is the repo's PRD directory (found as `/acs:create-prd` finds the
PRD, default `docs/product`), `<architecture_dir>` the repo's architecture
set (found by its `hld/tech-stack.md`, default `docs/architecture`) and
`<development_dir>` an existing `docs/development/`, else that default. The
feature is the ticket's first feature or the one `/acs:analyze-requirements`
confirms; a ticketless run names one in that skill's grouped ask.

**A run's own documents can stay in the workspace instead**
([ADR-0132](../../architecture/adr/0132-share-or-keep-run-documents-local.md)). A repo that keeps run documents local (`docs.share_run_documents:
false`, asked once and saved for one machine or the team) gets a Development
`analysis/` folder, `plan.md`, `test-cases.md`, `tech-design.md` and `api-contract.md`
in `runs/<run-id>/steps/<skill>/local/` rather than in a phase folder: they
are read by the run's later steps, never versioned, and never committed. The
living documents (PRD, roadmap, HLD, LLD, a feature's living analysis) always
go to the repo. A phase folder that resolves only to the built-in default is
created only after the user confirms it (or names another, saved as
`docs.<kind>_dir`).

**A ticket is not a document.** It lives in the workspace partition and in the
tracker; nothing writes `docs/tickets/<ID>/` or a `ticket.md`. Readers MUST
still look in an existing `docs/tickets/<ID>/` when a phase folder has no such
document, so a ticket started before ADR-0128 keeps its documents
([Legacy ticket folders](#legacy-ticket-folders)).

## Workspace folder

- The workspace is the single home for all pipeline **run state**. **All
  skills and hooks MUST read and write their state files in the workspace
  folder**, which is always `<main-checkout>/.acs/state-machine` — no
  setting locates it ([configuration.md](configuration.md)).
- The workspace MUST be resolvable to the **same physical location from
  every worktree of a repo** — that is the actual invariant, enabling
  **parallel tasks** (a worktree per ticket without state colliding or
  polluting the repo). It is achieved via the in-repo,
  main-checkout-anchored `.acs/state-machine` folder (gitignored, resolved
  from `git rev-parse --git-common-dir`), with no override (see ADR-0086,
  [ADR-0102](../../architecture/adr/0102-documents-are-found-not-configured.md)); a layout
  that cannot resolve a main checkout (bare repo, submodule) is refused —
  acs must be run from a regular git checkout.
- The workspace MUST ignore itself: the first state write under
  `.acs/state-machine/` creates `.acs/state-machine/.gitignore` containing
  `*`, so the workspace never shows up in `git status` whether or not the
  repo's root `.gitignore` names it. The root entries `/acs:setup` adds are
  no longer needed. Only a write creates the folder: a hook that only looks
  for state writes nothing, so a repo that never runs acs gets no folder
  ([ADR-0105](../../architecture/adr/0105-acs-runs-without-setup.md)).
- The workspace MUST be writable from a Claude Code worktree session.
  Such a session is refused the `Write`, `Edit` and `NotebookEdit` tools on
  any path in the main checkout, where the workspace is, so **no skill or
  agent writes a state file with the `Write` or `Edit` tool**: every state
  write goes through `acs.py write <path> [--append] [--run R]`, which runs
  from the session's own worktree, reads the content from stdin, writes it
  atomically (a temporary file, then a rename) and creates parent folders.
  `<path>` is absolute inside the workspace root, or relative to the run
  folder (`--run`, default the checkout's current run, which `acs.py
  context` reports as `run_id`/`run_dir`). A path outside the workspace
  root — by `..` or through a symlink — MUST be refused with exit 2 and
  nothing written, and so MUST a machine-owned ledger that has its own verb
  (`run.json`, `steps/<skill>/state.json`, `lock.json`, the indexes,
  `sessions/`, `active-agents/`, any `filemap.json`); a write prints
  `{"ok": true, "path": …, "bytes": …, "appended": …, "total_bytes": …}`.
  A coordinator hands its agents the absolute run folder, so an agent in an
  isolated worktree with no current run of its own still writes the right
  place. Repo files (code, tests, documents in the checkout) are still
  written with `Write`/`Edit` by the write roles
  ([ADR-0136](../../architecture/adr/0136-state-is-written-through-acs-write.md)).
- Under the Bash sandbox, which lets Bash write only the working directory,
  `$TMPDIR` and its `sandbox.filesystem.allowWrite` paths, the workspace is
  writable from a worktree only with an `allowWrite` entry naming its
  absolute path. `/acs:setup` offers that entry and writes it to the main
  checkout's `.claude/settings.local.json`
  ([skills.md](skills.md#setup-optional)). The workspace never moves for
  it: there is nothing to migrate.
- The workspace MUST be partitioned **by consumer repo, then by ticket
  and by run**: a ticket and its clarification ledger live under
  `<workspace>/<repo>/<ticket-id>/`, and every pipeline artifact of a run —
  ticket or not — under `<workspace>/<repo>/runs/<run-id>/`.
- `<repo>` is a stable identifier derived from the git remote
  (e.g. `owner-name`), falling back to the repo directory name when there is
  no remote. All worktrees of the same repo MUST resolve to the **same**
  `<repo>` partition — identity derives from the main repo / remote, never
  from the worktree path.

## Migrating an existing external workspace

- A repo owner moving state that an older acs kept in an external
  workspace (named by a retired `workspace_path` key) MUST use the manual
  migrator: `migrate_workspace.py --from <old-workspace-root> --to
  <repo>/.acs/state-machine --repo-root <repo-root> [--dry-run]` (contract in
  [cli.md](../../architecture/lld/acs/api/cli.md)). The migrator
  preflights — refusing to run while a `.lock` is held or an `in_progress`
  run exists anywhere under the old workspace's partition tree — then
  copies the repo's partition tree, verifies the copy, and only then
  removes the old tree; it is idempotent, so re-running after an
  interruption is safe.
- No setting points at the old location: every run resolves the in-repo
  workspace, so the old tree is no longer read once the migration succeeds.
  A leftover key for it in `.acs/settings.local.json` is a retired key —
  ignored, and safe to delete.

## Legacy ticket folders

- Nothing writes `docs/tickets/<ID>/` any more
  ([ADR-0128](../../architecture/adr/0128-requirements-from-any-container.md)).
  A folder written before that change MUST stay readable: every reader of a
  run's document looks in its phase folder first and, when that has no such
  file, in `docs/tickets/<ID>/<name>`. Nothing moves or deletes those
  folders; moving one into the phase folders is the repo owner's choice, and
  `git mv` is enough. `acs.py artifacts migrate` is retired: it reports and
  writes nothing.
- `acs.py artifacts show [--run R | --ticket ID]` reports, for one run, where
  each document resolves — its phase folder, the run's step folder (kept
  local), the legacy ticket folder or the partition — the diagnostic for
  "where did my tech-design.md go"; `acs.py docs where --doc <name>` says where the
  next write of a document goes and which answer is still owed.

## Requirements of a run

Every run, ticket or not, carries its requirements in the workspace
([ADR-0128](../../architecture/adr/0128-requirements-from-any-container.md)):

- A skill's arguments MUST be parsed into **sources**: a `<PREFIX>-<n>` token
  is a ticket, a token naming an existing file (repo-relative, absolute or
  `~`-expanded) is a document, and everything else is joined, in order, into
  one prompt. They may be mixed. `run.json.subject` stays ONE primary
  subject (ticket > document > prompt); the full list is `subject.sources`.
- `<run>/subject/sources.json` MUST record each source as `{kind, ref,
  sha256, copy}`. A document from outside the repo MUST be copied into the
  run as `<run>/subject/<n>-<basename>` and hashed; nothing is added to the
  repo for it.
- `<run>/requirements.md` MUST be regenerated from the sources, never edited
  by hand: a front block (run id, generated time, sources), `## Ticket <ID>`
  (title, description, acceptance criteria numbered `AC-1…`, features,
  `needs_design`), `## Prompt` (verbatim), `## Documents` (text inlined, other
  types cited by their run copy) and `## Refined` — written only by `acs.py
  requirements refine`, from `/acs:analyze-requirements`, into
  `<run>/requirements-refined.json`.
- A later step invoked with new sources MUST add them (deduplicated by hash,
  ticket or text) and regenerate; a source is never silently replaced.

## Layout

The repo's phase folders (committed by `/create-pr`, one folder per feature
and, inside it, one per ticket or run):

```
<repo>/
├── docs/product/                       # <prd_dir>
│   ├── prd.md
│   └── features/
│       └── bulk-export/                # a PRD feature's slug (acs.py slug)
│           └── analysis/               # Discovery: the feature's living analysis (ADR-0133; status/version/tickets/feature on every file)
│               ├── README.md           #   scope, AC-n, cross-cutting risks, questions, verdict, contexts table
│               └── order-export.md     #   one file per bounded context: impact map, rules, risks, open questions, API notes
├── docs/architecture/                  # <architecture_dir>
│   ├── hld/ ...
│   └── lld/
│       └── bulk-export/
│           ├── api/ data/ flows/ components/   # the living LLD, edited in place (ADR-0126; api/<interface>.md, ADR-0134)
│           ├── SHOP-122/               # Design records of one change: an epic
│           │   └── tech-design.md      # epics always carry the design; children read it from here
│           └── SHOP-123/
│               └── api-contract.md     # /create-api-contract's per-run record, linking the api/<interface>.md files it wrote
├── docs/development/                   # <development_dir>
│   └── bulk-export/
│       ├── SHOP-123/                   # Development documents of a ticket
│       │   ├── analysis/               # /analyze-requirements as a ship step: README.md + <context>.md
│       │   ├── plan.md                 # /create-impl-plan
│       │   └── test-cases.md           # /create-test-docs
│       └── export-as-csv-3f2a/         # ... and of a ticketless run, under its run id
└── docs/tickets/SHOP-90/               # LEGACY: read when a phase folder has no such file; never written
```

The workspace (gitignored, the run ledger):

```
<workspace>/
└── acme-shop/                          # one partition per consumer repo
    ├── tickets-index.json              # all tickets: id, type, status, parent/children
    ├── runs-index.json                 # all runs: id, workflow, subject, status, started/ended
    ├── counters.json                   # ticket id sequence (run ids derive from the subject; no allocator)
    ├── sessions/                       # per-checkout state for parallel worktree sessions
    │   └── <checkout-id>/              # ONE directory per checkout, not five prefixed files
    │       └── pointer.json            # the run AND step this checkout is on
    ├── archive/                        # runs of done tickets move here post-merge
    ├── SHOP-123/                       # THE TICKET: the workspace and the tracker are its only homes
    │   ├── ticket.json
    │   └── clarifications.json         # a ticket run's requirement Q&A ledger
    └── runs/
        ├── SHOP-1/                     # a ticket's run
        │   ├── run.json                # THE RUN MACHINE
        │   ├── subject/sources.json    # every source: kind, ref, sha256, run copy
        │   ├── requirements.md         # regenerated from the sources (ADR-0128)
        │   ├── baseline.json           # HEAD, branch and already-dirty paths at the first step start (ADR-0127)
        │   └── steps/<skill>/state.json
        ├── acs-create-prd-3f9a/        # a ticketless product-level run (here: /acs:create-prd)
        │   └── steps/create-prd/state.json   # incl. states.files, the uncommitted documents
        ├── fix-the-login-timeout-3f2a/ # a run started from a PROMPT (and documents), not a ticket
        │   ├── run.json
        │   ├── subject/
        │   │   ├── sources.json
        │   │   └── 1-spec.pdf          # a document attached from outside the repo, copied and hashed
        │   ├── requirements.md
        │   ├── requirements-refined.json   # analyze-requirements' refined AC, needs_design, features, feature
        │   └── clarifications.json     # a ticketless run's ledger lives in the run
        └── SHOP-123/                   # a story/task: the full pipeline
            ├── run.json                # THE RUN MACHINE: workflow, subject, loop iteration, status
            ├── lock.json               # held by the session working this run
            ├── lock-events.jsonl       # append-only audit of every `lock force-unlock` (who, why, what was broken)
            ├── subject/sources.json    # what this run is about: the ticket, documents, a prompt
            ├── requirements.md         # every step reads it (context.requirements); the ledger is the ticket's
            ├── agents/                 # runtime scratch: the active-agent records
            ├── handoff-context.md      # written by the PreCompact hook (session pause)
            ├── specs/                  # legacy input: pre-existing specs read by /code when present
            └── steps/
                ├── create-impl-plan/
                │   ├── state.json      # THE STEP MACHINE: this step's own invocations[]
                │   ├── result.json     # the post-hook's input
                │   ├── plan.md        # THE plan — one, at the step root; plan_sha256 hashes it
                │   ├── plan-approval.json   # written by plan-approval.py, never by a subagent
                │   └── iter-<n>/      # the AUDIT TRAIL: the plans there were
                ├── code/
                │   ├── state.json     # incl. invocations[-1].guard_events, the file-map guard's denials
                │   └── iter-<n>/execute.json · execute-<k>.json · task.json
                ├── review-code/
                │   ├── state.json · verdict.json
                │   └── iter-<n>/lens-<A..E>.md · adjudication.json · gate.json
                ├── docs-sync/state.json
                ├── create-pr/state.json      # incl. PR number/URL
                └── merge-pr/state.json
```

Repo-level files (all maintained by hooks):

- **`tickets-index.json`** — index of every ticket (id, type, status,
  parent/children, updated_at); lets skills and the user list work without
  scanning partitions.
- **`counters.json`** — the ticket id sequence counter
  (`<ticket_prefix>-<n>`). First allocation for a given `(repo_id, prefix)`
  partition is fail-closed (MAR-402): absent both `next` and
  `reconciled: true`, `allocate_ticket_id` refuses with exit 2 and a ranked,
  bounded, network-free local-evidence proposal rather than silently
  restarting the sequence at 1; a human confirms (or repairs a wrong/stuck
  reconciliation) via `--seed-next <n>` on either `new-ticket.py` or
  `acs.py step start --allocate`. Confirmed reconciliation is recorded via three
  additive optional fields: `reconciled` (boolean), `seed_source`
  (`committed-files`\|`git-history`\|`branch-names`\|`explicit-user`), and
  `seeded_at` (ISO-8601 UTC). The evidence scan's `observed_max` is surfaced
  only in the refusal message, for a human to read — it is never persisted.
  An already-populated `next` is treated as already reconciled — no prompt,
  no regression for existing repos.
- **`sessions/<checkout-id>.json`** — the per-checkout *current ticket*
  pointer written by the coordinator at skill start; `<checkout-id>` is
  derived from the absolute path of the repo checkout/worktree, so multiple
  parallel worktree sessions each have their own pointer
  ([hooks.md](hooks.md)).
- **`sessions/<checkout-id>-gate.json`** — the per-checkout gate evidence:
  the `PreToolUse(Skill)` hook records that it fired, and a run spends that
  record once, which is how acs tells a gated run from one on a host that
  never fired its hooks ([hooks.md](hooks.md)). It carries no session or
  transcript field.
- **`archive/`** — completed ticket partitions are moved here by
  `post-merge-pr` (the partition is archived, never deleted).

Product-level skills have **no repo-level state** and no ticket: each run is a
ticketless run over its invocation, and the skill's state
(`steps/create-prd/`, `steps/create-architecture/`) lives in that run's
partition; the skills' *outputs* (PRD, architecture doc set) live in the
consumer repo as uncommitted changes until `/create-pr "<prompt>"` commits them
([skills.md](skills.md#product-level-delivery-no-ticket)).

The **ticket** is the partition's `ticket.json` — the local source of truth —
and, when a tracker is configured, its remote copy. No `ticket.md` is written
([ADR-0128](../../architecture/adr/0128-requirements-from-any-container.md));
a legacy `docs/tickets/<ID>/ticket.md` (front matter of every field below
except `status`, plus `## Description`, `## Acceptance criteria` and a
`## Clarifications` mirror) is still read, and readers MUST return the same
dict from either shape. Skills read a run's acceptance criteria from its
requirements (`context.requirements`, `acs.py requirements show`), never
from `ticket.json`.

When a remote
tracker is configured, it MUST hold the local↔remote id mapping used for
two-way sync ([configuration.md](configuration.md)), e.g.:

```json
"external": { "provider": "github", "key": "456" }
```

`status` is **DERIVED from the run ledger, never stored** — a stored status
and a ledger that disagree is a class of bug the split removes rather than
manages. The derivation is:

| Derived status | When |
|----------------|------|
| `done` | the partition is archived, or `steps.merge-pr` is `completed`; for an epic, every child is `done` in `tickets-index.json`. |
| `in_review` | `steps.create-pr` is `completed`, or a product-level delivery skill completed with a PR reference in its state file. |
| `in_progress` | any step other than `create-ticket` has a status other than `skipped`; for an epic, any child is not `open`. |
| `open` | otherwise. |

`tickets-index.json` keeps mirroring the derived value so listings need not
re-derive it per ticket.

Key fields written by `/acs:create-ticket` and maintained by hooks:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Allocated ticket id, e.g. `SHOP-123` |
| `title` | string | Human-readable summary |
| `type` | `"epic"\|"story"\|"task"\|"bug"` | `bug` since ADR-0138; a bug runs like a story |
| `status` | `"open"\|"in_progress"\|"in_review"\|"done"` | **Derived** from the run ledger, never stored |
| `parent` | string\|null | Parent epic id; null for roots |
| `children` | string[] | Child ticket ids (epics only) |
| `features` | string[] | The PRD feature slugs the ticket traces to (ADR-0120); a child minted with `new-ticket.py --parent` (by `/acs:breakdown-ticket`) inherits its parent's unless `--features` is given (ADR-0138) |
| `external` | object\|null | Remote tracker mapping (`provider`/`key`) |
| `needs_design` | boolean | True for epics only; always `false` for stories/tasks/bugs (never offered or confirmed) — MAR-76 |
| `docs_only` | boolean | True when the change is docs/comments only; default false |
| `due_date` | string\|null | Optional delivery target date, ISO-8601 `YYYY-MM-DD`; `null` = no deadline set (MAR-15) |
| `severity` | `"critical"\|"high"\|"medium"\|"low"` | Optional, on a `bug` only (refused on any other type); a bug's impact, separate from `priority` (ADR-0138) |
| `reproduction` | string | Optional, on a `bug` only (refused on any other type); a bug's steps to reproduce (ADR-0138) |
| `expected` | string | Optional, on a `bug` only (refused on any other type); what a bug should do (ADR-0138) |
| `actual` | string | Optional, on a `bug` only (refused on any other type); what a bug does instead (ADR-0138) |
| `environment` | string | Optional, on a `bug` only (refused on any other type); the environment or version a bug was seen in (ADR-0138) |
| `created_at` | ISO-8601 datetime | Set at ticket creation, never changed |
| `updated_at` | ISO-8601 datetime | Refreshed on every save |

## State files

Each skill's post-hook writes a `<skill>-state.json` into the ticket
partition. State files are the **only** channel between steps — the
coordinator keeps no conversation history, so these files must be
self-sufficient.

Each state file MUST capture:

- **states** — the skill's current result data, consumed by the next skill
  (e.g. which specs were implemented, test/coverage results for `/code`);
- **findings** — anything discovered worth passing on (e.g. review findings,
  clarifications obtained from the user);
- **error details** — what went wrong, if anything;
- **invocations** — an **append-only array** of this step's invocations, each
  carrying that invocation's timestamps, **status**, and, when
  `interrupted`, its **stop reason** — plus the file-map guard's
  `guard_events` and the gate-enforcement verdict when there are any.
  No token count or other usage figure is recorded
  ([No usage recording](#no-usage-recording)). The array is `invocations`, not
  `runs`: a RUN is the whole pass over the workflow (`run.json`), and a step
  is invoked within it.

**No duplicated fields** — single source of truth:

- The **last invocation is the current state**: its `status` is what the step
  records, and therefore what the derived cursor (`acs.py run next`), the
  subject's derived status, and the pre-hook order advisory all read. It is
  NOT a gate condition — since the skills-independence refactor no pre-hook
  refuses a skill because another skill's last status is not `completed`.
  Status, stop reason, and last-updated time are NOT mirrored at top level
  (they would only drift).
- **The cursor is DERIVED, never stored:** the first step in workflow order
  that is not `completed`. A stored position beside the statuses it
  summarises is a second copy of one fact, and the two can disagree. When the
  cursor sits in a parallel group, the steps **due** are derived the same way:
  every member of that stage that is not `completed` (`acs.py run next`
  prints them as `due`).
- **One stage in progress (I1):** every step recorded `in_progress` MUST
  belong to one stage of the workflow — the members of one parallel group MAY
  all be `in_progress` at once, and nothing else may (ADR-0110). Step start
  refuses a step while a step of another stage is open, and `acs.py run
  check` reports a violation as an error.
- An invocation is appended with status **`in_progress`** by the coordinator
  at step start and finalized by the post-hook — so even a hard crash that
  skips the post-hook leaves the last invocation `in_progress`, which is not
  `completed`, so the cursor is still on that step and the next run
  reconciles ([workflow.md](workflow.md#resuming-a-ticket)).
- **Step statuses are exactly four**: `in_progress`, `completed`, `failed`,
  `interrupted`. A **`stop_reason`** belongs to an `interrupted` step only
  and MUST come from the closed set `session_end | needs_input |
  context_pressure`; a completed or failed step's narrative goes in
  `summary`. `handed_off` is not a status — it named a *reason* a step
  stopped, so it lost the "what"; a session pause is `interrupted` plus
  `stop_reason: context_pressure` and a handoff summary
  ([workflow.md](workflow.md#session-pause)). `skipped` is not a status
  either — a step that owes nothing is `completed` with the reason the plan's
  `## Contract` block gave (ADR-0096).
- Working time is **computed** from `started_at`/`ended_at`, never stored.
- `skill` and `run_id` do echo the directory the file sits in — kept
  deliberately so the file stays self-describing once moved to `archive/`,
  and as a cheap integrity check (path ↔ content mismatch = corruption).

**[ASSUMPTION]** Illustrative shape:

```json
{
  "skill": "code",
  "ticket_id": "SHOP-123",
  "states": {
    "specs_implemented": ["01-data-model", "02-api-endpoints"],
    "tests": { "passed": 42, "failed": 0, "coverage_percent": 93 }
  },
  "findings": [],
  "errors": [],
  "runs": [
    {
      "started_at": "2026-06-12T09:00:00Z",
      "ended_at": "2026-06-12T10:00:00Z",
      "status": "completed",
      "stop_reason": "all specs implemented, verifier passed"
    }
  ]
}
```

JSON Schemas for the ticket (`ticket.json`), `run.json` (its `subject`
carrying the optional `sources` list), `steps/<skill>/state.json`, a step's
`result.json`, the workflow file, the session pointer, `settings.json`
and `clarifications.json` are **shipped with the plugin**
(`schemas/`, fourteen of them). JSON Schema is the only validator: the XSD
layer and `validate_xml.py` are gone. Skills validate against the full schemas; hooks
perform lightweight stdlib-only structural checks
([hooks.md](hooks.md)).

## Requirements

- Writers are the subagents/hooks of the owning skill; other skills read but
  MUST NOT modify another skill's state file.
- Cross-ticket **reads** are allowed (e.g. a child ticket resolves its
  parent epic's `tech-design.md` (else a legacy `design.md`), from the epic's Design folder or, for an older
  epic, its legacy `docs/tickets/<ID>/` folder or its partition); cross-partition **writes** are limited
  to the defined parent-epic status updates performed by child hooks
  ([workflow.md](workflow.md#epic-fan-out)).
- The run's Development and Design folders
  (`<development_dir>/<feature>/<id>/`, `<architecture_dir>/lld/<feature>/<id>/`)
  and the legacy `docs/tickets/` tree are **control inputs**: the file-map
  guard refuses an executor subagent a write anywhere under them, with exit 2
  and a message naming it
  as a control input only the coordinator and the ticket skills write. An
  executor cannot widen or disarm its own scope by editing the ticket.
- Re-running a skill for the same ticket updates the **current state** in
  place and **appends to the `runs` array** — run history is append-only.
- State files MUST be valid JSON and SHOULD be human-readable
  (pretty-printed) — the workspace doubles as the audit trail a user can
  inspect.
- Skills MUST handle a partially-written/corrupt state file gracefully
  (treat as "not completed", report it, never crash the hook).

## Concurrency & parallel tickets

The intended way of working is **multiple sessions in parallel, one git
worktree per ticket**:

- Different tickets (different partitions) MUST be safely workable in
  parallel from separate worktrees; each session has its own
  `sessions/<checkout-id>.json` pointer, so ticket resolution never crosses
  sessions.
- **Locking**: a session working a ticket holds a **`.lock` file** in the
  ticket partition (containing checkout id, pid, and a timestamp). Pre-hooks
  exit 2 when another session holds the lock; the lock is released by the
  post-hook, or by a session pause
  ([workflow.md](workflow.md#session-pause)); a ticket handoff to a teammate
  leaves the sender's lock as it was
  ([workflow.md](workflow.md#ticket-handoff)). The lock is **re-entrant for the same checkout id** — resuming
  from the same worktree reclaims its own lock
  ([workflow.md](workflow.md#resuming-a-ticket)). **[ASSUMPTION]** A
  stale lock from a *different* checkout (no live process / very old
  timestamp) is reported to the user to clear manually rather than being
  auto-stolen. **[RESOLVED — MAR-530]** Still never auto-stolen, and no longer
  cleared by hand: `acs.py lock force-unlock` is the explicit path. It requires
  a stated reason and appends an audited entry — who broke it, why, and the
  lock document as it read at the time — to the partition's
  `lock-events.jsonl` (`schemas/lock-events.schema.json`) *before* removing the
  lock file, so a crash between the two leaves a recorded break with the lock
  still in place rather than a broken lock nobody can trace. Staleness is
  reported with the regime that produced it, because a pid from another
  container is not probeable here: a same-host lock is judged by process
  liveness, a cross-host one only by age.
- Product-level skills lock their ticketless run's partition like any
  other skill — no separate locking scheme.
- **Parallel instances inside one step** (ADR-0110) share the step's
  partition, lock and working tree. Each instance carries a slice id, and every file
  it writes under `steps/<skill>/iter-<n>/` carries it too
  (`<role>-<id>.json`, `<role>-<id>.md`, `authoring-<id>.md`,
  `<role>-<id>-message.xml`), so parallel siblings MUST never write the same
  file; the coordinator joins the slices into the unsliced names with
  `acs.py notes merge`. Each running agent is recorded in its own
  `agents/<agent_id>.json`, so no fan-out can lose a record to a
  read-modify-write race. Parallel writers commit nothing (ADR-0127): they
  write disjoint files into the working tree and list them in their reports.
- **A parallel group of steps** (ADR-0110) runs inside ONE `/ship` session
  under the run's one lock: its members are steps of the same run, each with
  its own `steps/<skill>/state.json`, so no second lock or pointer is needed.
- **Repo-level counter guard**: `update_index()` (the repo-level
  `tickets-index.json`) is wrapped in an `O_EXCL`-guarded
  critical section that serializes two writers finishing concurrently on the
  normal path. The spin is bounded, and exhausting it **fails closed**: the
  guard raises `GuardTimeout` and the write does not happen. A refused write is
  recoverable and visible; the fail-open write it replaced lost an update with
  nothing recording that it had. Every caller reports the refusal as
  `acs <command>: <reason>` with exit 2, releases any ticket lock it holds, and
  names which half of its writes is already durable. The budget is operable via
  `$ACS_GUARD_ATTEMPTS` (clamped to a ceiling, since only the pre-hook's own
  25-second bound applies otherwise). A guard file left behind by a writer that
  crashed is reclaimed automatically, but only once it is older than twice the
  configured budget **and** its recorded holder is not a process still running
  on this host — an age threshold alone cannot tell a crashed writer from a
  slow one, and reclaiming a live holder's guard puts two writers inside the
  critical section at once.

## No usage recording

The workspace records what the pipeline itself needs and nothing more: each
invocation's `started_at`/`ended_at`, status and stop reason (plus its
`guard_events` and gate-enforcement verdict), each step's `states`, findings
and errors, the run's progress in `run.json`, and each ticket's derived
status in `tickets-index.json`. Working time is computed from an
invocation's timestamps when a completion report prints it; it is never
stored or summed.

acs records **no usage**: no token count, no per-role or per-model
breakdown, no dollar figure, no per-run or per-repo totals, and it reads no
Claude Code transcript
([ADR 0104](../../architecture/adr/0104-no-usage-dashboards-no-usage-recording.md)).
Tokens, spend and time per ticket are Claude Code's to report — its own
`/cost`, the console, or its usage exports. A `metrics.json`, a `run.json`
`totals` object or an invocation's `tokens` left by an older version is
ignored.

## Epic ↔ child linkage

Links are stored in **both directions**: the epic's ticket document lists
`children`; each child's ticket document stores `parent`. The epic's status is
auto-managed — **In Progress** when work starts on any child, **Done** when
all children are merged ([workflow.md](workflow.md#epic-fan-out)) —
with child hooks performing the parent updates (first workflow skill run
marks In Progress; the last child's `post-merge-pr` marks Done).

## Lifecycle

When a ticket is merged/done, its partition is **archived** — moved to
`<workspace>/<repo>/archive/<ticket-id>/` by `post-merge-pr` — keeping the
full audit trail without cluttering the active workspace. Archived tickets
remain in `tickets-index.json` (status `done`).

### Ticket allocation on resume

`acs.py step start --allocate` MUST NOT mint a second ticket for work that
already has one, and MUST NOT let one run adopt another's partition. Reuse
is therefore resolved from EXPLICIT inputs only:

- `--ticket <id>`, for any skill; or
- `--args` for `/acs:create-ticket` alone, and only when the argument IS the
  id rather than prose citing one.

The session pointer and the branch name — which `resolve_ticket_id` consults
on the non-allocating path — MUST NOT be consulted here: two `/create-ticket`
runs passing neither would otherwise collapse two independent tickets into
one. Since ADR-0127 `--allocate` is `/acs:create-ticket`'s alone; the
product-level skills no longer mint a ticket.
