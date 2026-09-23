# Workspace & State Management

## Two stores: the repo docs tree and the workspace

A ticket's files live in two places, split by audience, and every requirement
below belongs to exactly one of them:

| | Repo docs tree | Workspace partition |
|---|----------------|---------------------|
| **Where** | `<repo>/docs/tickets/<ID>/` (fixed — no setting) | `<workspace>/<repo>/<ticket-id>/` |
| **Holds** | the human-facing ticket documents: `ticket.md`, `design.md`, `analysis.md`, `api-contract.md`, `plan.md`, `test-cases.md` | the run ledger: `run.json`, `steps/<skill>/state.json`, each step's `result.json` and `iter-<n>/` audit trail, verdicts, `lock.json`, `lock-events.jsonl`, `clarifications.json`, `agents/`, and the repo-level `tickets-index.json` / `runs-index.json` / `counters.json` / `sessions/` |
| **Versioned** | yes — committed on the ticket branch, reviewed in the PR | no — gitignored |
| **Written by** | the coordinator and the ticket skills; an executor MUST NOT write there (the file-map guard treats it as a control input) | hooks and the skills' own subagents |

The docs-tree location is **fixed, never discovered**, and the split has no
opt-out ([ADR-0102](../../adr/0102-documents-are-found-not-configured.md)).
Readers MUST still resolve a document by looking in the docs tree first and
the partition second, so a partition written before the split keeps working
unmigrated
([Migrating ticket documents into the repo](#migrating-ticket-documents-into-the-repo)).

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
  [ADR-0102](../../adr/0102-documents-are-found-not-configured.md)); a layout
  that cannot resolve a main checkout (bare repo, submodule) is refused —
  acs must be run from a regular git checkout.
- The workspace MUST be partitioned **by consumer repo, then by
  `<ticket-id>`**: every pipeline artifact for a ticket lives under
  `<workspace>/<repo>/<ticket-id>/`.
- `<repo>` is a stable identifier derived from the git remote
  (e.g. `owner-name`), falling back to the repo directory name when there is
  no remote. All worktrees of the same repo MUST resolve to the **same**
  `<repo>` partition — identity derives from the main repo / remote, never
  from the worktree path.

## Migrating an existing external workspace

- When an external workspace left by an older acs is detected for a repo
  (a retired `workspace_path` key still in a settings file, which
  `setup detect` reports under `retired_keys`),
  `/acs:setup` MUST detect it and SHOULD offer a user-confirmed
  migration into the in-repo default on the next re-run (ADR-0086; the
  MUST/SHOULD split for `/setup` itself is specified in
  [skills.md](skills.md) and not restated here).
- A repo owner who migrates without re-running `/acs:setup` MUST use
  the documented manual path instead: `migrate_workspace.py --from
  <old-workspace-root> --to <repo>/.acs/state-machine --repo-root
  <repo-root> [--dry-run]` (contract in
  [contracts.md](../../architecture/lld/contracts.md)). The migrator
  preflights — refusing to run while a `.lock` is held or an `in_progress`
  run exists anywhere under the old workspace's partition tree — then
  copies the repo's partition tree, verifies the copy, and only then
  removes the old tree; it is idempotent, so re-running after an
  interruption is safe.
- No setting points at the old location: every run resolves the in-repo
  workspace, so the old tree is no longer read once the migration succeeds.
  A leftover key for it in `.acs/settings.local.json` is an unknown key —
  ignored (named by `/acs:setup` as retired), and safe to delete.

## Migrating ticket documents into the repo

- A repo whose partitions predate the docs-tree split MUST keep working
  unmigrated: every reader falls back to the partition, so nothing breaks
  until the owner chooses to move.
- `acs.py artifacts migrate [--dry-run]` performs the one-shot move for every
  **live** partition (archived partitions are never migrated): it renders
  `ticket.json` into `docs/tickets/<ID>/ticket.md`, copies `design.md` and
  `phases/code/plan.md` into the same folder when they exist and no file is
  already there, writes `<partition>/ticket.json.moved` naming the new path,
  and unlinks `ticket.json`. It MUST be **idempotent** (a second run reports
  the already-migrated tickets and writes nothing new) and MUST refuse while
  a partition it still has to move holds a `.lock`.
- `acs.py artifacts show [--ticket ID]` reports, for one ticket, which store
  each document currently resolves from — the diagnostic for "where did my
  design.md go".

## Layout

The repo docs tree (committed, one folder per ticket):

```
<repo>/
└── docs/tickets/                       # fixed location, not a setting (ADR-0102)
    ├── SHOP-122/                       # an epic
    │   ├── ticket.md                   # front matter (every ticket.json field except status) + Description / Acceptance criteria / Clarifications
    │   └── design.md                   # epics always carry the design; children read it from here
    └── SHOP-123/                       # a story/task
        ├── ticket.md
        ├── analysis.md                 # /analyze-requirements
        ├── plan.md                     # /create-impl-plan
        ├── api-contract.md             # /create-api-contract (only when the analysis found an API surface change)
        └── test-cases.md               # /create-test-docs
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
    ├── tickets/<ticket-id>/ticket.json # only until artifacts migrate moves it
    └── runs/
        ├── SHOP-1/                     # a product-level delivery run (here: PRD)
        │   ├── run.json                # THE RUN MACHINE
        │   ├── subject/                # ticket.json | prompt.md | the document
        │   └── steps/create-prd/state.json   # incl. the docs PR reference
        ├── fix-the-login-timeout-3f2a/ # a run started from a PROMPT, not a ticket
        │   ├── run.json
        │   └── subject/prompt.md
        └── SHOP-123/                   # a story/task: the full pipeline
            ├── run.json                # THE RUN MACHINE: workflow, subject, loop iteration, status
            ├── lock.json               # held by the session working this run
            ├── lock-events.jsonl       # append-only audit of every `lock force-unlock` (who, why, what was broken)
            ├── subject/ticket.json     # what this run is about
            ├── requirements.md         # step 1's artifact, promoted: every later step reads it
            ├── clarifications.json     # requirement Q&A ledger (answers, open questions, assumptions)
            ├── agents/                 # runtime scratch: the active-agent records
            ├── handoff-context.md      # written by /acs:handoff
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

Product-level skills have **no repo-level state**: each run creates its own
delivery ticket, and the skill's state file (`create-prd-state.json`,
`create-architecture-state.json`, `create-project-state.json`) lives in
that ticket's partition; the skills' *outputs* (PRD, architecture doc set,
repo skeleton) live in the consumer repo
([skills.md](skills.md#product-level-delivery-tickets)).

The **ticket document** is the local source of truth for the ticket:
`docs/tickets/<ID>/ticket.md` when the docs tree is active, else the
partition's `ticket.json`. `ticket.md` carries every field below as YAML
front matter **except `status`**, plus a markdown body: `## Description`,
`## Acceptance criteria` (a numbered list) and `## Clarifications` (a
read-only mirror rendered from `clarifications.json`). Readers MUST accept
either shape and MUST return the same dict from both, so nothing downstream
has to know which store answered.

When a remote
tracker is configured, it MUST hold the local↔remote id mapping used for
two-way sync ([configuration.md](configuration.md)), e.g.:

```json
"external": { "provider": "jira", "key": "PROJ-456" }
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
| `type` | `"epic"\|"story"\|"task"` | |
| `status` | `"open"\|"in_progress"\|"in_review"\|"done"` | **Derived** from the run ledger, never written into `ticket.md` |
| `parent` | string\|null | Parent epic id; null for roots |
| `children` | string[] | Child ticket ids (epics only) |
| `external` | object\|null | Remote tracker mapping (`provider`/`key`) |
| `needs_design` | boolean | True for epics only; always `false` for stories/tasks (never offered or confirmed) — MAR-76 |
| `docs_only` | boolean | True when the change is docs/comments only; default false |
| `due_date` | string\|null | Optional delivery target date, ISO-8601 `YYYY-MM-DD`; `null` = no deadline set (MAR-15) |
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
  summarises is a second copy of one fact, and the two can disagree.
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
  stopped, so it lost the "what"; a deliberate handoff is `interrupted` plus
  `stop_reason: context_pressure` and a handoff summary
  ([workflow.md](workflow.md#session-handoff)). `skipped` is not a status
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

JSON Schemas for the ticket (`ticket.json`, whose field set `ticket.md`'s
front matter mirrors), `run.json`, `steps/<skill>/state.json`, a step's
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
  parent epic's `design.md`, from the epic's docs-tree folder or, for an
  unmigrated epic, its partition); cross-partition **writes** are limited
  to the defined parent-epic status updates performed by child hooks
  ([workflow.md](workflow.md#epic-fan-out)).
- The repo docs tree is a **control input**: the file-map guard refuses an
  executor subagent a write anywhere under
  `docs/tickets/`, with exit 2 and a message naming it
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
  post-hook, or by a session handoff
  ([workflow.md](workflow.md#session-handoff)). The lock is **re-entrant for the same checkout id** — resuming
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
- Product-level skills lock their **delivery ticket's** partition like any
  other skill — no separate locking scheme.
- **Cross-skill, phase-level fan-out** (`/acs:create-docs`) is a second,
  narrower parallelism shape layered on top of worktree-per-ticket: one
  unhooked coordinator mints **two independent delivery tickets** (one per
  eligible doc-bootstrap skill) via real `Skill`-tool Starts in the shared
  session checkout, then runs each phase (plan → execute → verify) as a
  parallel batch across both legs; each leg enters its own worktree at its
  own Delivery step's **Branch** sub-step, before that leg's Execute phase.
  Both tickets share the run's `checkout_id`
  for the Start/plan/execute/verify portion of the run — the disposition for
  this shared-checkout case is: pointer collisions are
  accepted, labeled degradations rather than a correctness
  bug, because every consumer of ticket identity gets the ticket id
  explicitly. Each
  leg's own `.lock`/pointer/state files are otherwise unaffected — the
  legs remain two ordinary, independently-resumable delivery tickets. See
  `docs/architecture/lld/flows/doc-bootstrap-fanout.md`.
- **Repo-level counter guard**: `update_index()` (the repo-level
  `tickets-index.json`) is wrapped in an `O_EXCL`-guarded
  critical section that serializes two legs finishing concurrently on the
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
([ADR 0104](../../adr/0104-no-usage-dashboards-no-usage-recording.md)).
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
on the non-allocating path — MUST NOT be consulted here. Product-level legs
run concurrently (a doc-bootstrap fan-out runs two at once) passing neither,
and resolving through either would collapse two independent delivery tickets
into one.
