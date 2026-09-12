# Hooks

Pre and post hooks are central to the workflow: they **check each skill's
inputs**, apply a small set of **safety brakes**, and **persist** each
skill's own state. Hooks are what make a skill's preconditions and its
recorded outcome deterministic, without relying on the model's memory or
goodwill.

Hooks do **not** enforce the pipeline's order. That order is declared in
`plugins/acs/workflows/ship.yaml` and walked by `/ship`
([workflow.md](workflow.md#pipeline)); a pre-hook's contribution to order is
one advisory stderr line, never a refusal.

## Requirements

- Every hooked skill — the eleven workflow skills, the eight product-level
  doc/bootstrap skills, and the conditional planning skill `/create-design` —
  MUST have a **pre-hook** and a **post-hook**.
- Hooks are implemented as **Python scripts**, named by convention:
  `pre-<skill>.py` and `post-<skill>.py`
  (e.g. `pre-code.py`, `post-code.py`).
- Hooks MUST read and write state files only in the **workspace folder**
  (`<workspace>/<repo>/…`), resolved via the `.acs` `settings.json`
  (see [configuration.md](configuration.md)). Most access stays inside
  the ticket's own partition, but hooks also maintain the repo-level files
  (`tickets-index.json`, `metrics.json`, `sessions/`), and
  the coordinator's `skill-start.py` MAY read the parent epic's partition to
  resolve its design state ([workspace-and-state.md](workspace-and-state.md)).
- A pre-hook MAY additionally **read** (never write) the ticket's documents
  in the repo docs tree (`docs/tickets/<ID>/`) to check the inputs its skill
  requires — `plan.md` for `/code`, `analysis.md` for `/create-api-contract`,
  `test-cases.md` for `/create-e2e-tests`
  ([workflow.md](workflow.md#where-a-tickets-artifacts-live)).

### Pre-hooks — input checks and safety brakes

A pre-hook runs before its skill and checks two things, and only these two:

**1. Inputs** — the artifacts and configuration the skill itself reads:

- Baseline checks shared by all pre-hooks: `settings.json` exists (else
  "run /setup"), `workspace_path` is resolvable (explicit override or
  derived default) and consistent across worktrees, and the `<ticket-id>`
  partition can be resolved.
- Skill-specific inputs — e.g. `pre-create-architecture.py` requires the PRD
  doc set; `pre-code.py` requires an approved `plan.md`;
  `pre-create-api-contract.py` requires `plan.md` **and** an `analysis.md`
  declaring `api_surface: true`; `pre-create-e2e-tests.py` requires a
  configured e2e suite **and** at least one e2e-typed case in
  `test-cases.md`.
- A missing input MUST be reported by naming the artifact, where it was
  looked for, and the skill that produces it.

**2. Safety brakes** — refusals that protect correctness rather than
sequence:

- another session holds the ticket's `.lock`
  ([workspace-and-state.md](workspace-and-state.md));
- the ticket is an **epic** and the skill implements work (`/code`,
  `/analyze-ticket`, `/create-impl-plan`) — epics are never implemented;
- `/create-pr` has a recorded `/code` run whose verifier did **not** pass;
- `/merge-pr` has no recorded PR reference.

A pre-hook MUST NOT refuse a skill because another skill has not completed.
The primitive that did so (`_require_completed`) was removed with the
skills-independence refactor; nothing in the gate layer reads a predecessor's
run status any more.

**3. Order advisory (never a refusal)** — when the skill IS a step of the
resolved `ship.yaml` and that step's `needs` are not all satisfied for this
ticket, the pre-hook MUST print exactly one line on stderr naming the
position and exit **0**:

```text
acs: docs-sync normally follows code in ship.yaml; code has not completed for SHOP-123
```

The advisory MUST be suppressed when `settings.workflow.advisories` is
`false` (default `true`), when the skill is not a step of the resolved
workflow, and whenever anything it needs cannot be read — it is best-effort
by construction and MUST never turn into a blocked gate. A refusal path never
carries it.

A pre-hook is also not purely a check: it **records** the
ticket-independent session-correlation marker (`session_id`,
`transcript_path`, `cwd`, `skill`) off the genuine `PreToolUse(Skill)` hook
envelope into `sessions/<checkout-id>-session.json`, inside its own
fail-open guard so a marker-write failure can never turn into a blocked
gate. The next skill's start step reads that marker (rejecting a foreign
`checkout_id` or one older than 15 minutes) to correlate real cost/time
measurement with this run (MAR-1,
[workspace-and-state.md](workspace-and-state.md)).

**Exit code contract:**

| Exit code | Meaning |
|-----------|---------|
| `0` | Ready — the skill proceeds. An order advisory may have been printed to stderr. |
| `2` | **Blocked** — the skill MUST NOT run. The hook's stderr message names the missing input (and the skill that produces it) or the brake that fired. |

Example: if no `plan.md` exists for ticket `SHOP-123`, then `pre-code.py`
exits 2 naming `/acs:create-impl-plan SHOP-123` and `/code` stops before
doing any work. If a `plan.md` exists but `/acs:analyze-ticket` never ran,
`/code` runs — after one advisory line.

### Post-hooks — state persistence

A post-hook runs after its skill and writes the skill's state into a JSON
file in the workspace partition:

- e.g. `post-code.py` writes `code-state.json` under
  `<workspace>/<repo>/<ticket-id>/`.
- The state file MUST record at least: the states, findings, and error
  details produced during the run, plus a new entry in the append-only
  `runs` array (timestamps, tokens, cost, status, stop reason). The **last
  `runs` entry is the current state** — `acs.py workflow next`, the ticket's
  derived status, and the order advisory all read `runs[-1].status` through
  the step ledger ([workspace-and-state.md](workspace-and-state.md));
  nothing is mirrored at top level.
- Post-hooks also update the ticket's **`pipeline-state.json`** step ledger,
  and the repo-level **`tickets-index.json`** and **`metrics.json`**
  (working time, tokens, cost per run — see
  [workspace-and-state.md](workspace-and-state.md)).
- If the skill ends abnormally (crash, interruption), the post-hook MUST
  still write a state with status `failed` or `interrupted` — never leave
  the previous state in place silently.
- A post-hook MUST be given a result document that states a `status`
  (via `--result-file`, JSON on stdin, or an explicit `--status`). An
  invocation with no result document, or one omitting `status`, is
  REFUSED with a non-zero exit — it is never recorded as a completed run.
- See [workspace-and-state.md](workspace-and-state.md) for the state
  file inventory and schemas.

## Hook inventory

Twenty hooked skills, each with one pre-hook and one post-hook:

| Skill | Pre-hook | Post-hook | Post-hook writes |
|-------|----------|-----------|------------------|
| `/create-prd` | `pre-create-prd.py` | `post-create-prd.py` | `create-prd-state.json` |
| `/create-requirements` | `pre-create-requirements.py` | `post-create-requirements.py` | `create-requirements-state.json` |
| `/create-architecture` | `pre-create-architecture.py` | `post-create-architecture.py` | `create-architecture-state.json` |
| `/create-project` | `pre-create-project.py` | `post-create-project.py` | `create-project-state.json` |
| `/create-principles` | `pre-create-principles.py` | `post-create-principles.py` | `create-principles-state.json` |
| `/create-standards` | `pre-create-standards.py` | `post-create-standards.py` | `create-standards-state.json` |
| `/create-quality` | `pre-create-quality.py` | `post-create-quality.py` | `create-quality-state.json` |
| `/create-operations` | `pre-create-operations.py` | `post-create-operations.py` | `create-operations-state.json` |
| `/standardize-project` | `pre-standardize-project.py` | `post-standardize-project.py` | `standardize-project-state.json` |
| `/create-ticket` | `pre-create-ticket.py` | `post-create-ticket.py` | `create-ticket-state.json` |
| `/create-design` | `pre-create-design.py` | `post-create-design.py` | `create-design-state.json` |
| `/analyze-ticket` | `pre-analyze-ticket.py` | `post-analyze-ticket.py` | `analyze-ticket-state.json` |
| `/create-impl-plan` | `pre-create-impl-plan.py` | `post-create-impl-plan.py` | `create-impl-plan-state.json` |
| `/create-api-contract` | `pre-create-api-contract.py` | `post-create-api-contract.py` | `create-api-contract-state.json` |
| `/create-test-docs` | `pre-create-test-docs.py` | `post-create-test-docs.py` | `create-test-docs-state.json` |
| `/code` | `pre-code.py` | `post-code.py` | `code-state.json` |
| `/docs-sync` | `pre-docs-sync.py` | `post-docs-sync.py` | `docs-sync-state.json` |
| `/create-e2e-tests` | `pre-create-e2e-tests.py` | `post-create-e2e-tests.py` | `create-e2e-tests-state.json` |
| `/create-pr` | `pre-create-pr.py` | `post-create-pr.py` | `create-pr-state.json` |
| `/merge-pr` | `pre-merge-pr.py` | `post-merge-pr.py` | `merge-pr-state.json` |

`/run-e2e-tests` (and the `/test` alias that forwards to it for one release)
is **unhooked**: it has no pre- or post-hook and records its own
`pipeline-state.json` step through `pipeline-step.py`. So are the utility
skills (`/setup`, `/ship`, `/handoff`, `/update`, `/install-hooks`,
`/metrics`, `/usage`, `/release`, `/create-docs`).

## Per-skill pre-hook conditions

Every row is an **input** (the skill cannot do its work without it) or a
**brake** (running would be unsafe). No row is an order requirement.

| Skill | Inputs | Brakes |
|-------|--------|--------|
| `/create-prd` | `/setup` done (settings exist) | — |
| `/create-requirements` | `/setup` done | — |
| `/create-ticket` | `/setup` done | — |
| `/create-architecture` | PRD doc set exists (`prd_path`) | — |
| `/create-project` | architecture doc set exists (`hld/tech-stack.md`) | — |
| `/create-principles` | architecture doc set exists | — |
| `/create-standards` | architecture doc set exists | — |
| `/create-quality` | architecture doc set exists | — |
| `/create-operations` | architecture doc set exists | — |
| `/standardize-project` | architecture doc set exists | — |
| `/create-design` | ticket resolves; ticket flagged `needs_design` | lock free |
| `/analyze-ticket` | ticket resolves | not an epic; lock free |
| `/create-impl-plan` | ticket resolves | not an epic; lock free |
| `/create-api-contract` | `plan.md` exists **and** `analysis.md` declares `api_surface: true` | lock free |
| `/create-test-docs` | ticket resolves | lock free |
| `/code` | ticket resolves; an approved `plan.md` exists | not an epic; lock free |
| `/docs-sync` | ticket resolves | lock free |
| `/create-e2e-tests` | an e2e suite is configured (`settings.e2e` / `settings.suites.e2e`) **and** `test-cases.md` lists ≥ 1 e2e case | lock free |
| `/create-pr` | ticket resolves | a recorded `/code` run must not have left `verifier_passed != true` (a ticket with **no** recorded code run is allowed); lock free |
| `/merge-pr` | ticket resolves | a PR reference is recorded: `/create-pr` completed (pipeline tickets), or the product-level skill completed with the PR reference in its state file (delivery tickets — [skills.md](skills.md#product-level-delivery-tickets)); lock free |

Three rows changed meaning with the skills-independence refactor and are
worth stating explicitly, because each used to be an order gate:

- `/create-design` no longer requires a completed `/create-ticket` run — the
  partition existing is the input, and that is what `/create-ticket` produces.
- `/docs-sync` no longer requires `/code` (or the post-code test step) to have
  completed; it re-derives doc impact from the branch diff, which is a real
  input it can check for itself.
- `/create-pr` no longer requires `/code` and `/docs-sync` completed. Its
  verifier-passed check survives as a **brake** and was narrowed: it refuses
  only a ticket that HAS a recorded code run whose verifier did not pass.

## Runtime & resolution rules

- **Run lifecycle**: at skill start the coordinator appends an
  **`in_progress` run entry** to the skill's state file; the post-hook
  finalizes it. A hard crash that skips the post-hook therefore still leaves
  `runs[-1].status == "in_progress"` (plus a stale `.lock`) — the workflow
  walk reads "not satisfied", so the step is simply ready again, and the next
  run reconciles
  ([workflow.md](workflow.md#resuming-a-ticket)). A deliberate session
  handoff finalizes the entry as `handed_off` and releases the lock
  ([workflow.md](workflow.md#session-handoff)).
- **Ticket id resolution for hooks**: the coordinator writes a
  **per-checkout pointer file** at skill start —
  `<workspace>/<repo>/sessions/<checkout-id>.json` (one per repo
  checkout/worktree, so parallel sessions never clash). Hooks read it to
  resolve the current ticket; the **branch name is the fallback** when no
  pointer exists. Product-level skills create their **delivery ticket** at
  start, so their hooks resolve a normal ticket partition like any other
  skill ([skills.md](skills.md#product-level-delivery-tickets)). Skills themselves resolve via argument → session context →
  branch name ([workflow.md](workflow.md#ticket-context)). Since MAR-1, the
  `sessions/` directory holds more than this pointer per checkout — see the
  session-correlation marker and cost-sample/cursor files in
  [workspace-and-state.md](workspace-and-state.md).
- **Python runtime**: hooks MUST be **stdlib-only Python 3** — no pip
  installs required on consumer machines.
- **Validation**: hooks perform lightweight structural validation of the
  JSON files they read/write (required keys, enum values) in stdlib code;
  full JSON Schema validation happens at skill level
  ([workspace-and-state.md](workspace-and-state.md)).

## Event binding (resolved at implementation)

Resolved against the current Claude Code plugin hooks API (no "skill
completed" event exists):

- **Pre-hooks** bind to the **`PreToolUse`** event matching the **`Skill`**
  tool: a dispatcher (`dispatch.py pre`) extracts the skill name from the
  tool input and runs that skill's gate **in its own process**, under a
  bounded alarm; exit 2 blocks the skill before it runs. The gate MUST fail
  closed — a gate that raises, overruns its bound, or exits early still ends
  as exit 2, because any other exit code reads as "not blocked". This fires for user-typed
  slash commands and model-initiated Skill calls alike (including the step skills
  `/ship` invokes directly).
- **Post-hooks** are invoked by the skill's **coordinator as its mandatory
  final step** (`post-<skill>.py --result-file …`) — their inputs (final
  status, findings, tokens, cost) exist only in the coordinator's context.
  Enforcement does not rely on the model: the coordinator registers an
  `in_progress` run entry at skill start (`skill-start.py`), so a skipped
  post-hook leaves the step recorded `in_progress` — never `completed`. Since
  the skills-independence refactor that fact no longer closes a gate; it
  makes the step **ready again** on the next `acs.py workflow next`, so the
  orchestrator re-runs it rather than the pipeline silently advancing past
  it.
- A **`SessionEnd`** hook (`dispatch.py session-end`) finalizes any run this
  checkout left `in_progress` as `interrupted` and releases its lock, so
  abnormal endings still write state.

See `plugins/acs/docs/INTERNALS.md` for the full implementation contract.
