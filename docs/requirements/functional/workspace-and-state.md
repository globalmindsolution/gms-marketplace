# Workspace & State Management

## Workspace folder

- The workspace is the single home for all pipeline state. **All skills and
  hooks MUST read and write their files in the workspace folder**, located
  via `workspace_path` in `settings.json`
  ([configuration.md](configuration.md)).
- The workspace MUST be resolvable to the **same physical location from
  every worktree of a repo** — that is the actual invariant, enabling
  **parallel tasks** (a worktree per ticket without state colliding or
  polluting the repo). It is achieved by default via the in-repo,
  main-checkout-anchored `.acs/state-machine` folder (gitignored, resolved
  from `git rev-parse --git-common-dir`), or via an explicit `workspace_path`
  override for anyone who needs a different location (see ADR-0085).
- The workspace MUST be partitioned **by consumer repo, then by
  `<ticket-id>`**: every pipeline artifact for a ticket lives under
  `<workspace>/<repo>/<ticket-id>/`. One `workspace_path` can therefore be
  shared by any number of consumer repos.
- `<repo>` is a stable identifier derived from the git remote
  (e.g. `owner-name`), falling back to the repo directory name when there is
  no remote. All worktrees of the same repo MUST resolve to the **same**
  `<repo>` partition — identity derives from the main repo / remote, never
  from the worktree path.

## Layout

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
    │   ├── ticket.json                 # lists children
    │   ├── pipeline-state.json
    │   ├── create-ticket-state.json
    │   ├── design.md                   # epics always carry the design; children inherit it
    │   └── create-design-state.json
    └── SHOP-123/                       # a story/task: full pipeline
        ├── .lock                       # held by the session working this ticket
        ├── ticket.json                 # output of /create-ticket (local source of truth); stores parent
        ├── pipeline-state.json         # compact step ledger for /ship and pre-hooks
        ├── clarifications.json         # requirement Q&A ledger (answers, open questions, assumptions)
        ├── phases/<skill>/             # per-phase artifacts: iter-<n>-plan.md (all triad skills; /code: plan.md, MAR-70) / -execute.json / -verify.md + XML snapshots; /code also: plan-approval.json (STANDARD/COMPLEX, written by plan-approval.py, not a subagent — MAR-73, slice 3 of MAR-69), plan-superseded-<k>.md (written by the coordinator on revocation, a byte-identical copy of the revoked plan.md, never deleted — MAR-74, slice 4 of MAR-69)
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
  (`<ticket_prefix>-<n>`).
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

`ticket.json` is the local source of truth for the ticket. When a remote
tracker is configured, it MUST hold the local↔remote id mapping used for
two-way sync ([configuration.md](configuration.md)), e.g.:

```json
"external": { "provider": "jira", "key": "PROJ-456" }
```

Key fields written by `/acs:create-ticket` and maintained by hooks:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Allocated ticket id, e.g. `SHOP-123` |
| `title` | string | Human-readable summary |
| `type` | `"epic"\|"story"\|"task"` | |
| `status` | `"open"\|"in_progress"\|"in_review"\|"done"` | Managed by hooks |
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

- The **last `runs` entry is the current state**: the next pre-hook's gate
  condition is `runs[-1].status == "completed"`. Status, stop reason, and
  last-updated time are NOT mirrored at top level (they would only drift).
- A run entry is appended with status **`in_progress`** by the coordinator
  at skill start and finalized by the post-hook — so even a hard crash that
  skips the post-hook leaves `runs[-1].status == "in_progress"`, which
  downstream gates treat as not completed and the next run reconciles
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

JSON Schemas for `ticket.json`, `pipeline-state.json`, each
`<skill>-state.json`, `settings.json`, `metrics.json`, and
`clarifications.json` are **shipped with the plugin** (`schemas/`). Skills validate against the full schemas; hooks
perform lightweight stdlib-only structural checks
([hooks.md](hooks.md)).

## Requirements

- Writers are the subagents/hooks of the owning skill; other skills read but
  MUST NOT modify another skill's state file.
- Cross-partition **reads** are allowed (e.g. a child ticket's
  `/code` reads the parent epic's `design.md`);
  cross-partition **writes** are limited to the defined parent-epic status
  updates performed by child hooks
  ([workflow.md](workflow.md#epic-fan-out)).
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
  auto-stolen.
- Product-level skills lock their **delivery ticket's** partition like any
  other skill — no separate locking scheme.

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
  a run's window, a disclosed limitation rather than a silent one.

## Epic ↔ child linkage

Links are stored in **both directions**: the epic's `ticket.json` lists
`children`; each child's `ticket.json` stores `parent`. The epic's status is
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
