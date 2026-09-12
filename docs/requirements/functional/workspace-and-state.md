# Workspace & State Management

## Two stores: the repo docs tree and the workspace

A ticket's files live in two places, split by audience, and every requirement
below belongs to exactly one of them:

| | Repo docs tree | Workspace partition |
|---|----------------|---------------------|
| **Where** | `<repo>/<settings.artifacts.tickets_path>/<ID>/` (default `docs/tickets/<ID>/`) | `<workspace>/<repo>/<ticket-id>/` |
| **Holds** | the human-facing ticket documents: `ticket.md`, `design.md`, `analysis.md`, `api-contract.md`, `plan.md`, `test-cases.md` | the run ledger: `<skill>-state.json`, `pipeline-state.json`, `phases/<skill>/`, verdicts, `.lock`, `lock-events.jsonl`, `clarifications.json`, `active-agents`, and the repo-level `tickets-index.json` / `counters.json` / `metrics.json` / `sessions/` |
| **Versioned** | yes — committed on the ticket branch, reviewed in the PR | no — gitignored |
| **Written by** | the coordinator and the ticket skills; an executor MUST NOT write there (the file-map guard treats it as a control input) | hooks and the skills' own subagents |

`artifacts.tickets_path` set to **`null`** turns the split off: every
document stays in the workspace partition exactly as before the split, and
every reader falls back to it. Readers MUST therefore resolve a document by
looking in the docs tree first and the partition second, so a partition
written before the split keeps working unmigrated
([Migrating ticket documents into the repo](#migrating-ticket-documents-into-the-repo)).

## Workspace folder

- The workspace is the single home for all pipeline **run state**. **All
  skills and hooks MUST read and write their state files in the workspace
  folder**, located via `workspace_path` in `settings.json`
  ([configuration.md](configuration.md)).
- The workspace MUST be resolvable to the **same physical location from
  every worktree of a repo** — that is the actual invariant, enabling
  **parallel tasks** (a worktree per ticket without state colliding or
  polluting the repo). It is achieved by default via the in-repo,
  main-checkout-anchored `.acs/state-machine` folder (gitignored, resolved
  from `git rev-parse --git-common-dir`), or via an explicit `workspace_path`
  override for anyone who needs a different location (see ADR-0086).
- The workspace MUST be partitioned **by consumer repo, then by
  `<ticket-id>`**: every pipeline artifact for a ticket lives under
  `<workspace>/<repo>/<ticket-id>/`. One `workspace_path` can therefore be
  shared by any number of consumer repos.
- `<repo>` is a stable identifier derived from the git remote
  (e.g. `owner-name`), falling back to the repo directory name when there is
  no remote. All worktrees of the same repo MUST resolve to the **same**
  `<repo>` partition — identity derives from the main repo / remote, never
  from the worktree path.

## Migrating an existing external workspace

- When an existing external `workspace_path` is detected for a repo,
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
- Once the migration succeeds, the repo owner MUST remove the
  `workspace_path` key from `.acs/settings.local.json`, so that future runs
  resolve the in-repo default instead of the old override.

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
- A repo that does not want the split sets `artifacts.tickets_path` to
  `null`; `artifacts migrate` then refuses rather than half-moving anything.
- `acs.py artifacts show [--ticket ID]` reports, for one ticket, which store
  each document currently resolves from — the diagnostic for "where did my
  design.md go".

## Layout

The repo docs tree (committed, one folder per ticket):

```
<repo>/
└── docs/tickets/                       # settings.artifacts.tickets_path
    ├── SHOP-122/                       # an epic
    │   ├── ticket.md                   # front matter (every ticket.json field except status) + Description / Acceptance criteria / Clarifications
    │   └── design.md                   # epics always carry the design; children read it from here
    └── SHOP-123/                       # a story/task
        ├── ticket.md
        ├── analysis.md                 # /analyze-ticket
        ├── plan.md                     # /create-impl-plan
        ├── api-contract.md             # /create-api-contract (only when the analysis found an API surface change)
        └── test-cases.md               # /create-test-docs
```

The workspace (gitignored, the run ledger):

```
<workspace>/
└── acme-shop/                          # one partition per consumer repo
    ├── tickets-index.json              # all tickets: id, type, status, parent/children
    ├── counters.json                   # ticket id sequence (next ticket number)
    ├── metrics.json                    # repo aggregates: ticket/PR counts, time, tokens, cost
    ├── sessions/                       # per-checkout state for parallel worktree sessions
    │   ├── <checkout-id>.json          # current ticket id for that checkout/worktree
    │   ├── <checkout-id>-session.json  # ticket-independent session-correlation marker (MAR-1)
    │   ├── <checkout-id>-cost-samples.jsonl  # append-only statusLine cost samples, rotated in place (MAR-1)
    │   └── <checkout-id>-cost-cursor.json    # allocation cursor into the cost-sample log (MAR-1)
    ├── archive/                        # partitions of done tickets move here post-merge
    ├── SHOP-1/                         # a product-level delivery ticket (here: PRD)
    │   ├── ticket.json                 # type task, e.g. "Product definition (PRD)"
    │   ├── pipeline-state.json         # marks the flow as product-level
    │   └── create-prd-state.json       # incl. the docs PR reference
    ├── SHOP-122/                       # an epic: grouping + design
    │   ├── ticket.json.moved           # the epic's ticket.md and design.md live in the docs tree
    │   ├── pipeline-state.json
    │   ├── create-ticket-state.json
    │   └── create-design-state.json
    └── SHOP-123/                       # a story/task: full pipeline
        ├── .lock                       # held by the session working this ticket
        ├── lock-events.jsonl           # append-only audit of every `lock force-unlock` (who, why, what was broken)
        ├── ticket.json.moved           # pointer left by `acs.py artifacts migrate`: {ticket_id, moved_to, relative, migrated_at}
        │                               # (an unmigrated partition, or artifacts.tickets_path: null, keeps ticket.json here instead)
        ├── pipeline-state.json         # compact step ledger: what /ship's workflow walk and the order advisory read
        ├── clarifications.json         # requirement Q&A ledger (answers, open questions, assumptions)
        ├── phases/<skill>/             # per-phase artifacts: iter-<n>-plan.md / -execute.json / -verify.md + XML snapshots; /create-impl-plan also: plan-approval.json (STANDARD/COMPLEX, written by plan-approval.py, not a subagent — MAR-73, slice 3 of MAR-69), plan-superseded-<k>.md (written by the coordinator on revocation, a byte-identical copy of the revoked plan.md, never deleted — MAR-74, slice 4 of MAR-69). The approved plan.md itself is a human-facing document and lives in the docs tree.
        ├── create-ticket-state.json
        ├── specs/                      # legacy input: pre-existing specs (1..n, conform to the design) read by /code when present; new tickets have none — /code self-authors the fold content instead
        │   ├── 01-data-model.md
        │   └── 02-api-endpoints.md
        ├── code-state.json             # written by post-code.py; incl. verifier review findings + runs[-1].escalations audit trail
        ├── docs-sync-state.json        # written by post-docs-sync.py; the /docs-sync run ledger
        ├── create-pr-state.json        # incl. PR number/URL
        └── merge-pr-state.json
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
  `skill-start.py --allocate`. Confirmed reconciliation is recorded via three
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
- **`sessions/<checkout-id>-session.json`**,
  **`sessions/<checkout-id>-cost-samples.jsonl`**,
  **`sessions/<checkout-id>-cost-cursor.json`** (MAR-1) — three additional
  per-checkout files backing real cost/time measurement: a
  ticket-independent session-correlation marker (`session_id`/
  `transcript_path`/`cwd`/`skill`, written by a pre-hook inside its own
  fail-open guard, rejected by the consuming skill if stale past 15 minutes
  or from a foreign `checkout_id`); an append-only log of `statusLine`
  cost samples, rotated in place once it exceeds 64 KiB (no `.1` sibling);
  and the allocation cursor marking how much of that log has already been
  charged to a run ([hooks.md](hooks.md)).
- **`metrics.json`** — per-repo aggregates (see [Metrics](#metrics)).
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

`tickets-index.json` keeps mirroring the derived value so listings and
metrics need not re-derive it per ticket.

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
- **runs** — an **append-only array** of run entries, each carrying that
  run's timestamps, token counts, cost, **status**, and **stop reason**.

**No duplicated fields** — single source of truth:

- The **last `runs` entry is the current state**: `runs[-1].status` is what
  the step ledger records, and therefore what `acs.py workflow next`, the
  ticket's derived status, and the pre-hook order advisory all read. It is
  NOT a gate condition — since the skills-independence refactor no pre-hook
  refuses a skill because another skill's `runs[-1].status` is not
  `completed`. Status, stop reason, and last-updated time are NOT mirrored at
  top level (they would only drift).
- A run entry is appended with status **`in_progress`** by the coordinator
  at skill start and finalized by the post-hook — so even a hard crash that
  skips the post-hook leaves `runs[-1].status == "in_progress"`, which the
  workflow walk treats as unsatisfied (the step is ready again) and the next
  run reconciles
  ([workflow.md](workflow.md#resuming-a-ticket)).
- Run statuses: `in_progress`, `completed`, `failed`, `interrupted`, and
  `handed_off` — a deliberate session handoff, where the entry also carries
  a handoff summary ([workflow.md](workflow.md#session-handoff)).
- Working time is **computed** from `started_at`/`ended_at`, never stored.
- `skill` and `ticket_id` do echo the filename and partition folder — kept
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
      "session_id": "...",
      "transcript_path": "...",
      "checkout_id": "...",
      "tokens": { "input": 152000, "output": 38000, "cache_creation": 0, "cache_read": 0 },
      "cost_usd": 4.21,
      "cost_basis": "measured",
      "cost_scope": "session_total",
      "excluded_cost_usd": 0.0,
      "excluded_token_share": 0.0,
      "role_usage": [ { "role": "executor", "input": 152000, "output": 38000, "cache_creation": 0, "cache_read": 0, "cost_usd": 4.21, "cost_basis": "measured" } ],
      "model_usage": [ { "model": "claude-sonnet-4-6", "input": 152000, "output": 38000, "cache_creation": 0, "cache_read": 0, "cost_usd": 4.21, "cost_basis": "measured" } ],
      "status": "completed",
      "stop_reason": "all specs implemented, verifier passed"
    }
  ]
}
```

JSON Schemas for the ticket (`ticket.json`, whose field set `ticket.md`'s
front matter mirrors), `pipeline-state.json`, each
`<skill>-state.json`, `settings.json`, `metrics.json`, and
`clarifications.json` are **shipped with the plugin** (`schemas/`). Skills validate against the full schemas; hooks
perform lightweight stdlib-only structural checks
([hooks.md](hooks.md)).

## Requirements

- Writers are the subagents/hooks of the owning skill; other skills read but
  MUST NOT modify another skill's state file.
- Cross-ticket **reads** are allowed (e.g. a child ticket resolves its
  parent epic's `design.md`, from the epic's docs-tree folder or, when the
  tree is off, the epic's partition); cross-partition **writes** are limited
  to the defined parent-epic status updates performed by child hooks
  ([workflow.md](workflow.md#epic-fan-out)).
- The repo docs tree is a **control input**: the file-map guard refuses an
  executor subagent a write anywhere under
  `<settings.artifacts.tickets_path>/`, with exit 2 and a message naming it
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
  this shared-checkout case is: pointer/marker/cursor collisions are
  accepted, labeled degradations (statusline shows only one leg; the losing
  leg's cost sampling degrades to `unavailable`) rather than a correctness
  bug, because every consumer of ticket identity gets the ticket id
  explicitly and `cost_basis` is never fabricated for the losing leg. Each
  leg's own `.lock`/pointer/state files are otherwise unaffected — the
  legs remain two ordinary, independently-resumable delivery tickets. See
  `docs/architecture/lld/flows/doc-bootstrap-fanout.md`.
- **Repo-level counter guard**: `update_index()`/`update_metrics()` (repo-level
  `tickets-index.json`/`metrics.json`) are wrapped in an `O_EXCL`-guarded
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

## Metrics

The workspace records effort and cost at every level; post-hooks maintain
all of it:

- **Per run**: each `runs` entry records `started_at`/`ended_at` (working
  time is computed from them), token counts (input/output), and cost. Runs
  finalized outside a post-hook — `handed_off` (session handoff) and
  `interrupted` (SessionEnd safety net) — are counted in the repo aggregates
  too, so `metrics.json` and the per-ticket roll-up never diverge.
- **Per ticket**: `pipeline-state.json` rolls up totals across all skills
  and runs for the ticket.
- **Per repo** (`metrics.json`): ticket counts (by status and type), PR
  counts (created, merged), and total working time, tokens, and cost.
- **Measured, not self-reported (MAR-1, ADR 0082).** The coordinator's XML
  result carries no token/cost figures at all — the standing `[ASSUMPTION]`
  this bullet used to record is resolved, not merely reworded. A run's
  `session_id`/`transcript_path` are captured from the genuine
  `PreToolUse(Skill)` hook envelope by a session-correlation marker,
  threaded onto the run entry at `skill-start.py`. At finalize time,
  `usage_reader.py` reads real token counts (all four `message.usage`
  classes) from that exact recorded transcript plus its `subagents/`
  subtree — never a constructed path — and buckets them by role, including a
  first-class `coordinator` bucket. A dollar figure is sourced from Claude
  Code's own real-time cost computation, sampled off the opt-in `statusLine`
  hook and apportioned across roles by measured token share
  (`cost_sampler.py`) via a cursor-consumed, non-overlapping partition that
  makes double-charging structurally impossible. acs owns no price table.
  Every figure carries a basis label — `measured` / `apportioned` /
  `unavailable` — never fabricated, never zero-padded; coverage is
  contingent on `statusLine` opt-in and on an unconsumed sample existing in
  a run's window, a disclosed limitation rather than a silent one. The
  dollar-cost double-charging guarantee above (`cost_sampler.py`'s
  checkout-scoped cursor) is unaffected by fan-out and holds unconditionally,
  in every topology including the one below. A separate, narrower guarantee —
  subagent-role token attribution (`usage_reader.py`) being immune to
  cross-session contamination — is scoped to topologies where each ticket
  runs in its own session — true of worktree-per-ticket generally, but not of
  the "Cross-skill, phase-level fan-out" shape two headings above, where
  `/acs:create-docs`'s two legs share one session and their subagent work is
  folded into shared role buckets by suffix alone, so subagent-role token
  accounting is not immune to cross-contamination in that one specific case.
  See ADR 0082's "Amendment — MAR-1" for the mechanism.

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
remain in `tickets-index.json` (status `done`) and in the metrics
aggregates.

### Ticket allocation on resume

`skill-start.py --allocate` MUST NOT mint a second ticket for work that
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
