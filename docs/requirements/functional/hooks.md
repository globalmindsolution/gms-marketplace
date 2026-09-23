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

- Every hooked skill — the eleven workflow skills, the five product-level
  doc/bootstrap skills, and the conditional planning skill `/create-design` —
  MUST have a **pre-hook** and a **post-hook**.
- Hooks are implemented as **Python scripts**, named by convention:
  `pre-<skill>.py` and `post-<skill>.py`
  (e.g. `pre-code.py`, `post-code.py`).
- Hooks MUST read and write state files only in the **workspace folder**
  (`<workspace>/<repo>/…`), resolved via the `.acs` `settings.json`
  (see [configuration.md](configuration.md)). Most access stays inside the
  run's own directory (`runs/<run-id>/`), but hooks also maintain the
  repo-level files (`tickets-index.json`, `runs-index.json`,
  `sessions/`), and `acs step start` MAY read the parent epic's run to
  resolve its design state ([workspace-and-state.md](workspace-and-state.md)).
- A pre-hook MAY additionally **read** (never write) the ticket's documents
  in the repo docs tree (`docs/tickets/<ID>/`) to check the inputs its skill
  requires — `plan.md` for `/code`, and the plan's `## Contract` block, from
  which a step that owes nothing records its evidenced no-op
  ([workflow.md](workflow.md#where-a-tickets-artifacts-live)).

### Pre-hooks — input checks and safety brakes

A pre-hook runs before its skill and checks two things, and only these two:

**1. Inputs** — the artifacts and configuration the skill itself reads:

- Baseline checks shared by all pre-hooks: `settings.json` exists (else
  "run /setup"), the workspace (always `<main-checkout>/.acs/state-machine`,
  no override) can be derived and is consistent across worktrees, and the
  `<ticket-id>` partition can be resolved.
- Skill-specific inputs — e.g. `pre-code.py` requires an approved `plan.md`;
  `pre-create-api-contract.py` requires `plan.md` **and** an `analysis.md`
  declaring `api_surface: true`; `pre-create-e2e-tests.py` requires a
  configured e2e suite **and** at least one e2e-typed case in
  `test-cases.md`.
- A missing input MUST be reported by naming the artifact, where it was
  looked for, and the skill that produces it.
- A repo **document** (the PRD, the architecture set) is not a pre-hook
  input: no setting says where one lives, so the skill that needs it finds
  it at Start and stops, naming the skill that produces it, when there is
  none ([ADR-0102](../../adr/0102-documents-are-found-not-configured.md)).

**2. Safety brakes** — refusals that protect correctness rather than
sequence:

- another session holds the ticket's `.lock`
  ([workspace-and-state.md](workspace-and-state.md));
- the ticket is an **epic** and the skill implements work (`/code`,
  `/analyze-requirements`, `/create-impl-plan`) — epics are never implemented;
- `/create-pr` has a recorded `/code` run whose verifier did **not** pass;
- `/merge-pr` has no recorded PR reference.

A pre-hook MUST NOT refuse a skill because another skill has not completed.
The primitive that did so (`_require_completed`) was removed with the
skills-independence refactor; no gate reads a predecessor's **position**. One
brake reads a predecessor's recorded state, and only for the artifact inside
it: `/merge-pr` accepts a PR reference only from a step recorded `completed`,
because a reference written by a step that never finished is not evidence that
a PR exists. That brake names an artifact, never a position, and refuses
nothing for being early ([ADR 0101](../../adr/0101-gating-skills-that-are-not-workflow-steps.md)).

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

A pre-hook is also not purely a check: before the gate passes or blocks, it
**records** that it fired — the skill and the time, into
`sessions/<checkout-id>-gate.json` — inside its own fail-open guard so a
write failure can never turn into a blocked gate. The next skill's start
step spends that evidence once (rejecting a foreign `checkout_id` or one
older than 15 minutes) to tell a gated run from one on a host that never
fired acs's hooks ([workspace-and-state.md](workspace-and-state.md)). It
records no session or transcript field: acs measures no usage
([ADR 0104](../../adr/0104-no-usage-dashboards-no-usage-recording.md)).

**Exit code contract:**

| Exit code | Meaning |
|-----------|---------|
| `0` | Ready — the skill proceeds. An order advisory may have been printed to stderr. |
| `2` | **Blocked** — the skill MUST NOT run. The hook's stderr message names the missing input (and the skill that produces it) or the brake that fired. |

Example: if no `plan.md` exists for ticket `SHOP-123`, then `pre-code.py`
exits 2 naming `/acs:create-impl-plan SHOP-123` and `/code` stops before
doing any work. If a `plan.md` exists but `/acs:analyze-requirements` never ran,
`/code` runs — after one advisory line.

**`acs gate --skill <name>` MUST answer exactly what the pre-hook would
answer** — the same exit code and the same stderr for the same subject,
including the input-fallback lines, the safety brakes and the order advisory —
**and MUST NOT write anything doing it**: no run created, no lock taken, no
step opened, no no-op settled. When the checkout has no run yet, the gate
judges the run the subject *would* open, projected in memory and never
persisted ([ADR 0101](../../adr/0101-gating-skills-that-are-not-workflow-steps.md)).

### Post-hooks — state persistence

A post-hook runs after its skill and writes the skill's state into a JSON
file in the workspace partition:

- e.g. `post-code.py` writes `steps/code/state.json` under
  `<workspace>/<repo>/runs/<run-id>/`.
- The state file MUST record at least: the states, findings, and error
  details produced during the step, plus a new entry in the append-only
  **`invocations`** array (timestamps, status, stop reason).
  The array is `invocations`, not `runs`, because a RUN is the whole pass
  over the workflow and a step is invoked within it. The **last invocation is
  the current state** — the derived cursor, the subject's derived status and
  the order advisory all read it
  ([workspace-and-state.md](workspace-and-state.md)); nothing is mirrored at
  top level.
- A step's status is one of **`in_progress | completed | failed |
  interrupted`**. A `stop_reason` belongs to an `interrupted` step only and
  MUST come from the closed set `session_end | needs_input |
  context_pressure`; a completed or failed step's narrative goes in
  `summary`. `handed_off` and `skipped` are not statuses.
- Post-hooks also update **`run.json`**, and the repo-level
  **`tickets-index.json`** and **`runs-index.json`** (see
  [workspace-and-state.md](workspace-and-state.md)). They record no usage
  figure.
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
| `/acs:create-docs` | `pre-create-docs.py` | `post-create-docs.py` | `create-docs-state.json` (one partition per doc set's delivery ticket) |
| `/standardize-project` | `pre-standardize-project.py` | `post-standardize-project.py` | `standardize-project-state.json` |
| `/create-ticket` | `pre-create-ticket.py` | `post-create-ticket.py` | `create-ticket-state.json` |
| `/create-design` | `pre-create-design.py` | `post-create-design.py` | `create-design-state.json` |
| `/analyze-requirements` | `pre-analyze-requirements.py` | `post-analyze-requirements.py` | `analyze-requirements-state.json` |
| `/create-impl-plan` | `pre-create-impl-plan.py` | `post-create-impl-plan.py` | `create-impl-plan-state.json` |
| `/create-api-contract` | `pre-create-api-contract.py` | `post-create-api-contract.py` | `create-api-contract-state.json` |
| `/create-test-docs` | `pre-create-test-docs.py` | `post-create-test-docs.py` | `create-test-docs-state.json` |
| `/code` | `pre-code.py` | `post-code.py` | `code-state.json` |
| `/docs-sync` | `pre-docs-sync.py` | `post-docs-sync.py` | `docs-sync-state.json` |
| `/create-e2e-tests` | `pre-create-e2e-tests.py` | `post-create-e2e-tests.py` | `create-e2e-tests-state.json` |
| `/create-pr` | `pre-create-pr.py` | `post-create-pr.py` | `create-pr-state.json` |
| `/merge-pr` | `pre-merge-pr.py` | `post-merge-pr.py` | `merge-pr-state.json` |

The utility skills (`/setup`, `/ship`, `/handoff`, `/update`,
`/install-hooks`, `/release`) are **unhooked**: they
have no pre- or post-hook and take no position in a run. The `/test` alias is
removed — `/run-e2e-tests` is the skill, and it is hooked like any other
step.

## Per-skill pre-hook conditions

Every row is an **input** (the skill cannot do its work without it) or a
**brake** (running would be unsafe). No row is an order requirement.

| Skill | Inputs | Brakes |
|-------|--------|--------|
| `/create-prd` | `/setup` done (settings exist) | — |
| `/create-requirements` | `/setup` done | — |
| `/create-ticket` | `/setup` done | — |
| `/create-architecture` | `/setup` done (the skill itself checks for a PRD at Start) | — |
| `/create-project` | `/setup` done (the skill itself checks for the architecture set's `hld/tech-stack.md` at Start) | — |
| `/acs:create-docs` | `/setup` done (the skill itself checks for the architecture set at Start, once for every doc set) | — |
| `/standardize-project` | `/setup` done (the skill itself checks for the architecture set at Start) | — |
| `/create-design` | ticket resolves; ticket flagged `needs_design` | lock free |
| `/analyze-requirements` | ticket resolves | not an epic; lock free |
| `/create-impl-plan` | ticket resolves | not an epic; lock free |
| `/create-api-contract` | `plan.md` exists **and** `analysis.md` declares `api_surface: true` | lock free |
| `/create-test-docs` | ticket resolves | lock free |
| `/code` | ticket resolves; an approved `plan.md` exists | not an epic; lock free |
| `/docs-sync` | ticket resolves | lock free |
| `/create-e2e-tests` | an e2e suite is configured (`settings.e2e` / `settings.suites.e2e`) **and** `test-cases.md` lists ≥ 1 e2e case | lock free |
| `/create-pr` | ticket resolves | a recorded `/code` run must not have left `verifier_passed != true` (a ticket with **no** recorded code run is allowed); lock free |
| `/merge-pr` | ticket resolves | a PR reference is recorded: `/create-pr` completed (pipeline tickets), or the product-level skill completed with the PR reference in its state file (delivery tickets — [skills.md](skills.md#product-level-delivery-tickets)); lock free |

**A skill the workflow does not name is still gated.** `/create-design` and
`/merge-pr` are deliberately not steps of `ship.yaml` and MUST NOT become
steps; their brakes are therefore consulted from a subject-ticket table
**before** the resolved workflow is read, not from the step gate behind it. A
safety brake is not switchable off by editing a workflow file, and adding
either skill to a workflow would add the run machinery to it rather than
remove the brake ([ADR 0101](../../adr/0101-gating-skills-that-are-not-workflow-steps.md)).

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
  the last invocation `in_progress` (plus a stale lock) — the cursor is
  derived as the first step that is not `completed`, so the step is simply
  due again, and the next run reconciles
  ([workflow.md](workflow.md#resuming-a-ticket)). A deliberate session
  handoff finalizes the invocation `interrupted` with
  `stop_reason: context_pressure` and releases the lock
  ([workflow.md](workflow.md#session-handoff)).
- **Run resolution for hooks**: the coordinator writes a **per-checkout
  pointer file** at step start —
  `<workspace>/<repo>/sessions/<checkout-id>/pointer.json`, carrying the
  current run and step (one directory per repo checkout/worktree, so parallel
  sessions never clash). Hooks read it to
  resolve the current ticket; the **branch name is the fallback** when no
  pointer exists. Product-level skills create their **delivery ticket** at
  start, so their hooks resolve a normal ticket partition like any other
  skill ([skills.md](skills.md#product-level-delivery-tickets)). Skills themselves resolve via argument → session context →
  branch name ([workflow.md](workflow.md#ticket-context)). The
  `sessions/` directory also holds each checkout's gate evidence — see
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
  status, stop reason, findings) exist only in the coordinator's context.
  Enforcement does not rely on the model: the coordinator records the step
  `in_progress` at skill start (`acs.py step start --step <name>`), so a
  skipped post-hook leaves it `in_progress` — never `completed`. Since the
  skills-independence refactor that fact no longer closes a gate; because the
  cursor is derived as the first step that is not `completed`, it makes the
  step **due again** on the next `acs.py run next`, so the orchestrator
  re-runs it rather than the pipeline silently advancing past it.
- A **`SessionEnd`** hook (`dispatch.py session-end`) finalizes any run this
  checkout left `in_progress` as `interrupted` and releases its lock, so
  abnormal endings still write state.

See `plugins/acs/docs/INTERNALS.md` for the full implementation contract.
