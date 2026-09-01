# Usage Walkthroughs

How a developer drives `acs` day to day. Commands are typed in a Claude Code
session inside the consumer repo. Everything here follows the requirements
in the sibling files; this doc adds no new rules, it shows them in action.

## One-time setup (any repo)

```text
cd acme-shop
/setup
  → scope?            project            (.acs/settings.json + gitignored .acs/settings.local.json)
  → workspace_path?   (default: derives to <main-checkout>/.acs/state-machine — no answer needed;
                        set it only to point somewhere else)
  → ticket_prefix?    SHOP               (suggested from the repo name)
  → coverage 90, merge_strategy squash, tracker local  (defaults, editable)
```

### Existing product (brownfield)

```text
/create-prd            # reverse-engineers a baseline PRD from code + docs,
                       #   asks you to confirm open points
                       # → delivery ticket SHOP-1, docs PR "[SHOP-1] Product definition"
/merge-pr SHOP-1       # after you review the PR yourself

/create-architecture   # reverse-engineers HLD (C4 1–3, data model, deployment)
                       #   + LLD (key flows you confirm), all Mermaid
                       # → delivery ticket SHOP-2, docs PR
/merge-pr SHOP-2
```

### Fresh product (greenfield)

Same as above, but `/create-prd` and `/create-architecture` *elicit* instead
of reverse-engineer, and one extra step scaffolds the repo:

```text
/create-project        # layout per the C4 containers, build config,
                       #   test framework + coverage tooling, lint, CI,
                       #   minimal green vertical slice
                       # → delivery ticket SHOP-3, bootstrap PR (CI runs on it)
/merge-pr SHOP-3
```

## Ship a feature — umbrella mode

```text
/ship Add wishlist support so customers can save products for later
```

What happens (you are asked clarifying questions along the way):

1. `/create-ticket` — analyzes the prompt against the PRD, codebase, and
   docs; creates epic `SHOP-4` with **no children** (`children: []`). Its
   `/create-design` runs next; then `/acs:create-ticket SHOP-4 --fan-out`
   mints children `SHOP-5`, `SHOP-6` from the design's slices (you confirm
   the breakdown). Epic flips to **In Progress** when work starts.
2. Per child: `/create-design` (or the child inherits the epic's design) →
   `/code` (TDD against 90% coverage, verifier review loop
   ≤3 iterations, docs + architecture updated) → `/docs-sync` → `/create-pr`.
3. `/ship` **stops before merge** — it never merges for you.

Then, per PR, after your own review:

```text
/merge-pr SHOP-5       # readiness check → squash merge → delete branch →
                       #   clean worktree → ticket done (+ tracker sync) →
                       #   partition archived; epic auto-done after last child
```

## Ship a ticket — step-by-step mode

Every step is invocable on its own; hooks enforce the order:

```text
/create-ticket Fix flaky checkout total rounding     # → SHOP-7 (task)
/code SHOP-7                                          # TDD + review loop
                                                       #   (self-authors specs/ since none exist)
/docs-sync SHOP-7
/create-pr SHOP-7
/merge-pr SHOP-7
```

The ticket id argument is optional when the context is unambiguous —
resolution order is explicit argument → session context → branch name.

## Ship an existing ticket

```text
/ship SHOP-123         # continues from the first incomplete step
                       #   (ledger decides; gates re-verify)

# ticket only exists in Jira / GitHub Projects?
/create-ticket PROJ-456    # imports it: local id + external mapping,
                           #   then normal analysis/clarification
/ship SHOP-124             # ship the imported ticket
```

Interrupted or handed-off tickets resume the same way — the coordinator
reconciles recorded progress (re-runs tests for specs marked implemented)
before continuing.

## Merge a one-off non-ticket PR

For a legitimate change that never went through the pipeline (a hotfix, a
chore), label the PR `acs-exempt` and land it with the sanctioned exempt-merge
path instead of a raw `gh pr merge`:

```text
/merge-pr --pr 42      # (or #42 / a PR URL) readiness check → merge →
                       #   delete branch; no ticket, no tracker, no archive
```

It refuses and points you back to `/merge-pr <ticket-id>` if the PR is actually
ticket-backed.

## Parallel tickets with worktrees

```text
git worktree add ../shop-SHOP-5 && cd ../shop-SHOP-5
/ship SHOP-5           # session A

# meanwhile, in another terminal:
git worktree add ../shop-SHOP-6 && cd ../shop-SHOP-6
/ship SHOP-6           # session B
```

Each worktree gets its own `sessions/<checkout-id>.json` pointer; each
ticket partition is locked by its session, so the two never collide. The
workspace resolves to the same main-checkout-anchored location from every
worktree, precisely so both worktrees share one state store (ADR-0086).

## Long session? Hand off

```text
/handoff
  → flushed in-flight work + decisions to SHOP-5's partition
  → run entry marked handed_off, lock released
  → continue with:  /code SHOP-5   (in a fresh session)
```

Crashed or interrupted instead? Just re-run the same skill — the
coordinator sees the `in_progress` run entry and reconciles (e.g. re-runs
the tests for specs marked implemented) before continuing.

## Changing product scope

```text
/create-ticket Let customers share wishlists publicly
  → diverges from the PRD (sharing is out-of-scope) — amend the PRD?
/create-prd            # confirmed amendment → new delivery ticket + docs PR
```

## Where everything lives

| Location | Contents |
|----------|----------|
| Consumer repo | Code, `docs/product/` (PRD), `docs/architecture/` (HLD/LLD), ADRs, scaffold |
| `<workspace>/<repo>/` | `tickets-index.json`, `counters.json`, `metrics.json`, `sessions/`, `archive/`, one partition per ticket (states, specs, designs, runs with time/tokens/cost) |

Inspect progress and spend anytime: `tickets-index.json` for status across
tickets, `metrics.json` for per-repo totals, a ticket's
`pipeline-state.json` for where it stands in the pipeline.

Or run the two read-only in-session dashboards — both write nothing and make
no network call:

- **`/metrics`** (PM view) — delivery summary (including an additive G25
  escalation line: event count, fast-lane-escalated count, de-escalation
  count, silent-reversal count), throughput by status/type,
  pipeline funnel + distinct PRs, ISSUES, PROGRESS (per-epic burn-up),
  DEADLINE (on-track/overdue derived from `due_date`; degrades to "not set" when
  no ticket has a parseable `due_date` — B1),
  coverage achieved vs target, review iterations before the verifier passed,
  and lead + cycle time per ticket.
- **`/usage`** (usage view) — usage summary (total cost, time, runs, API
  duration, and six averages: avg working time and cost per ticket and per
  merged PR, plus avg API duration per ticket and per merged PR), cost + time
  per ticket by pipeline step with the four averages
  (avg working time and cost per ticket and per merged PR). Each ticket row
  also expands into a per-skill sub-row per pipeline step showing that
  skill's own API-duration figure alongside its wall-clock **step span**
  (`step_api_duration`/`step_order`) — mirroring Claude Code's own `/usage`
  split between wall-clock and API time; the API-duration cell renders the
  literal `unavailable` marker uniformly whether that skill's entry is
  structurally absent (e.g. the unhooked `test` pipeline step) or present
  with its own basis `unavailable`, never a bare "no data" at this per-skill
  scope. Plus token burn by
  role (coordinator/planner/executor/verifier/other, plus an `unattributed`
  bucket for same-window tokens with no attribution or attributed to a
  different acs skill than the run's own — `coordinator` is always rendered,
  `other`/`unattributed` appear whenever the ticket has any such spend),
  each bucket additionally showing its repo-scope **token-share** and
  **cost-share** percentage of panel 6's own totals (`token_share_pct`/
  `cost_share_pct`, computed once after all runs are summed),
  and usage by model — input/output/cache-write/cache-read tokens and cost
  per model, at both repo and per-ticket scope. Its cost figure apportions
  the run's full charged delta by token share with no unattributed
  exclusion, unlike the role-scoped figure above, so the by-model total can
  exceed the role-scoped attributed-only total by the excluded/unattributed
  share — a named reconciliation identity, not a discrepancy.
  Plus usage by ticket — input/output/cache-write/cache-read tokens and cost
  per role, per ticket, each role additionally showing its **token-share**
  and **cost-share** percentage of that ticket's own totals (ticket-scoped,
  distinct from panel 6's repo-scope shares above — a different denominator
  over the same underlying data, not a conflicting figure). Each ticket also
  opens with a ticket-scope API-duration figure (`api_duration_ms`/
  `api_duration_basis`, folded across that ticket's own skills) and a
  `skills[]` breakdown — one row per hooked skill the ticket ever ran, its
  own run time, API duration, and basis, plus per-run detail — that degrades
  independently of the role table above: a skill with run entries but no
  duration ever measured/apportioned still gets a row (null duration, basis
  `unavailable`) rather than being dropped, and the list is empty only when
  the ticket has zero run entries for every hooked skill; a role with no
  measured cost in that ticket renders `no data` for its cost figure and
  `unavailable` for its cost-share, independent of any sibling role in the
  same ticket.
  This render-layer `unavailable` marker (used only on a cost-share cell
  with no measured cost, in either panel) is a distinct thing from the
  `cost_basis` field's own pre-existing `unavailable` enum value described
  below — the former is a share computation with no denominator to divide
  by, the latter is a run-level fact about how that run's cost was priced;
  they happen to share a string but never the same field.
  Every cost figure carries a `cost_basis` — `measured` (the
  attributed-token share of the real session-window dollar delta sampled
  from Claude Code's own statusLine cost payload — that delta net of the
  excluded/unattributed token share, per the "drop, don't redistribute"
  policy — still sourced directly from Claude Code's own real number, never
  an acs-invented estimate), `apportioned` (that same attributed share split
  further across roles by measured token share), or `unavailable` (no
  fabricated number; excluded from sums, not zero-padded) — plus a
  `cost_scope`: `session_total` or `main_session_only` (a statusLine total
  proved not to include subagent spend) on a charge, reused as
  `no_unconsumed_sample_in_window` or `cost_total_reset` to carry the
  degraded reason when `cost_usd` is `null`. There is no
  `pricing_snapshot_date`: acs owns no price table, so no derived-from-a-price-list
  framing applies (MAR-1, ADR 0082).
