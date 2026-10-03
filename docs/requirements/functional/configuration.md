# Configuration & `/setup`

The `acs` plugin must work on **different consumer repos**. Configuration is
stored as `settings.json` under an `.acs` folder, and is optional: every key
has a working default, so a repo with no settings file at all runs every skill
([ADR-0105](../../adr/0105-acs-runs-without-setup.md)). The optional `/setup`
skill sets the ticket prefix and the settings of the CI gates it
installs; every other key, `ticket_prefix` included, is edited by hand,
validated against `settings.schema.json`.

## Scopes & files

| Scope | Path | Git | Use |
|-------|------|-----|-----|
| User | `~/.acs/settings.json` | n/a | Defaults shared across all of a user's repos. |
| Project (shared) | `<repo>/.acs/settings.json` | **committed** | Team-shared, repo-specific settings (tracker, models, coverage, merge strategy). |
| Project (local) | `<repo>/.acs/settings.local.json` | **gitignored** | Machine-specific overrides of any key. |

- `/setup` writes only the project file `<repo>/.acs/settings.json` —
  conventions are the team's, so there is no scope question. The user file
  is edited by hand.
- `/setup` MUST NOT write a value equal to its built-in default, and removes
  one an earlier run wrote (reported as `defaulted`), so the file carries
  only choices: a key absent from it resolves to the default.
- Machine-specific keys belong in the **gitignored `settings.local.json`**;
  `/setup` writes no key there, but ensures the file is listed in the repo's
  `.gitignore`.
- Resolution order (per-key merge, most specific wins):
  **`settings.local.json` → `settings.json` → `~/.acs/settings.json`**.
- Re-running `/setup` **updates the existing files in place**, preserving
  keys it does not touch.

## Keys

| Key | Type | Default | Required | Description |
|-----|------|---------|----------|-------------|
| `merge_strategy` | string | `"squash"` | No | How `/merge-pr` merges: `squash` \| `merge` \| `rebase`. |
| `ticket_prefix` | string | `"ACS"` | No | Prefix for generated ticket ids (`<prefix>-<sequence>`): `ACS-1`, `ACS-2`, … by default. A repo that wants its own — e.g. `SHOP` for a shop product — sets it by hand in `.acs/settings.json`; `/setup` does not ask. Two repos that keep the default both mint `ACS-1`; ids are per-repo state and never cross repos, so a repo that shares a tracker with others sets its own. Changing it later strands the older ids' branches. The per-repo sequence counter lives in the workspace (`counters.json`). |
| `tests` | object | unset | No | Everything about running tests: `{ "coverage"?, "unit"?, "e2e"?, "<name>"? }`. `coverage` is a number in `(0, 100]`, default `90` — the `/code` TDD coverage target (missing it is a hard fail) and the floor of the CI tests gate, exported to the gate as `ACS_COVERAGE`. `unit` (`{ "command", "setup"? }`) is the suite of the **CI tests + coverage gate** scaffolded by `/acs:setup` (Step 3, opt-in): `command` runs the suite and MUST fail on a coverage shortfall — delegate to the tool (e.g. `pytest --cov --cov-fail-under=$ACS_COVERAGE`). It is installed as `.github/workflows/acs-tests.yml` + `.acs/ci/run-tests.py`, which read the **committed** project `.acs/settings.json` (the CI runner has no acs install); a merge gate once made a required status check (`Tests & coverage`) on a protected default branch. Every key of `tests` except `coverage` is a **named suite** `{ "command", "setup"?, "teardown"? }`; `/acs:run-e2e-tests` runs all of them, or a `--suite`-selected subset, capturing pass/fail results to an auditable workspace artifact. `e2e` is the end-to-end suite: unset = no e2e suite; when configured, spec test plans state the e2e impact, `/code` authors the declared e2e tests in the same changeset, and `/acs:review-code`'s final gate runs the full suite (`setup` → `command` → `teardown` always) — a green run is required for a passing verdict. `/create-project` scaffolds the harness and proposes this block for greenfield repos with a user-facing surface. `tests.e2e` is also the **single opt-in signal** for the CI required merge gate — no dedicated `tests.e2e.ci` enable key exists, or is ever introduced (see the e2e merge gate note below). |
| `test_coverage_percent`, `suites`, top-level `e2e`, `per_iteration` | — | — | — | **Removed.** Replaced by `tests.coverage`, `tests.<name>` and `tests.e2e` (`per_iteration` was accepted and inert, and is gone). Until a settings file is migrated every acs skill refuses to start, naming the keys; `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" settings migrate [--write]` rewrites an old-shape file (dry-run by default). The old CI-gate keys `tests.command` / `tests.setup` are now `tests.unit.command` / `tests.unit.setup`. |
| `enforcement` | — | — | — | **Removed.** There is no enforcement block. The CI convention check scaffolded by `/acs:setup` (`.github/workflows/acs-conventions.yml` + `.acs/ci/check-conventions.py`) enforces one rule — the PR description names its ticket (the acs id, a `#<n>` issue reference or an issue link, [ADR-0106](../../adr/0106-ci-checks-the-ticket-link-only.md)) — with fixed exemptions: the `acs-exempt` label and `release/*`, `dependabot/*`, `renovate/*` branches. The `ACS` label `/create-pr` applies and `/merge-pr --pr` reads is fixed too (`acs_lib.conventions`). The local `commit-msg`/`pre-push` hooks and `/acs:install-hooks` are gone. A block a repo still carries is accepted and ignored. |

**e2e required merge gate (`/acs:setup`, opt-in).** When `tests.e2e` is already configured — by hand; `/acs:setup` does not configure
a suite — `/acs:setup` offers the gate at Step 2 and Step 3 scaffolds
`.github/workflows/acs-e2e.yml` + `.acs/ci/run-e2e.py` — the same
committed-settings-reading pattern as the tests gate, independent of it (a
repo can gate on one, both, or neither). **Opt-in invariant**: when
`tests.e2e` is unset, the gate is never offered — no files copied, no
`gh api` call, zero new behavior. `run-e2e.py` resolves the command from
`tests.e2e`, runs `setup` → `command` → `teardown`
(teardown always, in a `finally`; a non-zero teardown is a logged warning and
never flips a green `command` result to red), and exits with `command`'s
status. On `admin=true` **and** explicit user consent, Step 4 extends the
SAME `required_status_checks.contexts` array the conventions and tests gates
use with the literal `"E2E suite"` context — never a second, competing `PUT` —
only after the check has reported a conclusion at least once (avoids the
"unknown context" 422). Otherwise (no admin, or decline): Step 4 prints the
exact `gh api … /protection` command **once** and continues — never
hard-fails `/acs:setup` (the report-once safeguard). No new settings key is
introduced by any of this.
| `models` | object | inherit | No | Which Claude model **and reasoning effort** each subagent runs on: `models.<skill>.<role>`, an object with optional `model` (an alias, a full model id or `inherit`) and `effort` (`low`, `medium`, `high`, `xhigh`, `max` or `inherit`). The skills and roles are the agents the plugin ships; `acs.py settings scaffold --write` adds every entry a file lacks. See [Subagent models](#subagent-models). |
| `tracker` | object | `{ "provider": "local" }` | No | Ticket tracking backend. `provider` is `local` (default) or `github` (GitHub Projects). Tickets are always stored **local-first** in the workspace; when `github` is configured, tickets sync **two-way** with the remote tracker, and `ticket.json` keeps the local↔remote id mapping. Access goes through the `gh` CLI, the only tracker transport. Provider-specific sub-keys live under `tracker.github`. Jira is not supported. |
| `formats` | — | — | — | **Removed.** Branch, commit and PR-title style are the model's to follow (it reads `CLAUDE.md`, `CONTRIBUTING.md` and recent history). What a script must parse is fixed in `acs_lib.conventions`: the branch name `<type>/<ticket_id>-<slug>` (ticket detection depends on the id), the built-in template names (`pr-default`, `epic-default`, `story-default`, `task-default`, `design-default`; a repo's `.acs/templates/<name>.md` replaces one) and an epic's `[EPIC] ` title prefix. A block a repo still carries is accepted and ignored. |
| `evals` | object | unset | No | **Read by nothing.** Accepted by the schema and ignored: its only reader was the behavioural-eval harness's forge tier, retired when the eval suite moved to `claude plugin eval` case files. It never affected the hook layer, so it changes no acs runtime behavior. Kept in the schema so a consumer's existing settings stay valid; removing it is a schema change for its own release. |

More keys are expected as requirements grow — the file format MUST tolerate
unknown keys for forward compatibility.

### Document and workspace locations

No key locates a document or the workspace
([ADR-0102](../../adr/0102-documents-are-found-not-configured.md)). A skill
finds a repo document the way any Claude Code session does: `CLAUDE.md`
(project instructions, loaded in every session) and whatever docs index it or
the repo points at (e.g. `docs/README.md`), then a Glob/Grep search by file
name or content. Found → it uses that location. Not found → it creates the
document at the conventional default:

| Document | Default location | Produced / consumed by |
|----------|------------------|------------------------|
| PRD | `docs/product/prd.md` + `docs/product/roadmap.md` | Bootstrapped and amended by `/create-prd`; `/create-architecture` requires and is verified against it; `/create-ticket` traces tickets to it. |
| Architecture set | `docs/architecture/` (`hld/tech-stack.md` is its sentinel file) | **HLD** (C4 levels 1–3, data model, deployment, tech stack) and **LLD** (per-flow sequence diagrams, contracts). Bootstrapped by `/create-architecture`, consumed by `/create-design`, kept current by `/code`. |
| Living requirements | `docs/requirements/` with `functional/` and `non-functional/` subfolders (an existing set's own subfolder names are followed) | The standing behavioral contract, one file per feature area: `/code` merges each ticket's acceptance criteria and behavior-defining clarifications into the touched area's file; `/create-ticket` reads it as the area's current behavior and flags contradictions. |
| ADRs | `docs/adr/` | `/code` commits the accepted decision records from the ticket's `design.md` here, so decisions outlive archived ticket partitions. |
| Quality / operations / principles / standards sets | `docs/quality/`, `docs/operations/`, `docs/principles/`, `docs/standards/` | Bootstrapped and maintained by `/acs:create-docs <set>`; `standards` also reads the principles set, when the repo has one, as an upstream grounding input. |
| Machine-readable API contract files | `docs/api/` | Written by `create-api-contract` when the plan adds or changes an interface. |

Two locations are **fixed, never discovered**: a ticket's own documents live
at `docs/tickets/<ID>/`, and the workspace — the folder where all skills and
hooks read/write ticket state — is always `<main-checkout>/.acs/state-machine`,
a gitignored folder anchored to the repo's main checkout
(`git rev-parse --git-common-dir`), so every worktree resolves to the same
physical location without state being duplicated/dirtied per worktree
(ADR-0086). Neither has an override. The workspace ignores itself: the first
state write under it creates `.acs/state-machine/.gitignore` containing `*`,
so it stays out of `git status` whether or not `/setup` ever added a root
`.gitignore` entry (ADR-0105).

### Format placeholders

Inline format strings (`branch_name`, `commit_message`, `pr_title`, ticket
titles) use `{placeholder}` syntax. The supported vocabulary:

| Placeholder | Meaning | Usable in |
|-------------|---------|-----------|
| `{ticket_id}` | Local ticket id (e.g. `SHOP-123`) | all |
| `{type}` | Ticket type: `epic` \| `story` \| `task` | all |
| `{title}` | Ticket title | `pr_title`, ticket titles |
| `{slug}` | Kebab-case slug of the title (lowercase `a–z0–9-`, ≤ 40 chars) | `branch_name` |
| `{summary}` | Short generated summary of the change | `commit_message`, `pr_title` |
| `{external_key}` | Remote tracker key (empty when not synced) | all |
| `{ticket_ref}` | The tracker's native reference when the ticket is synced (`#399` on GitHub), else the local id | `pr_title` |

The built-in defaults are `{type}/{ticket_id}-{slug}` for `branch_name`,
`{ticket_id} {summary}` for `commit_message`, and `{title}` for `pr_title`.
The PR title carries no ticket id by default, because the PR description's
Ticket section links the ticket; a repo that wants the id in its titles uses
`{ticket_id}` or `{ticket_ref}` (ADR-0105).

An **unknown placeholder is a validation error**: `/setup` and the pre-hooks
reject the format string (exit 2) rather than passing it through silently.

Product-level skills create a real **delivery ticket** for each run
([skills.md](skills.md#product-level-delivery-tickets)), so their
branches, commits, and PRs use ordinary ticket ids — the placeholder
vocabulary has no special cases.

### Description templates

Long descriptions (PR body, ticket descriptions) come from **pre-defined
markdown templates** shipped with the plugin:

| Template | Used by | Sections |
|----------|---------|----------|
| `pr-default` | `/create-pr` | Summary, Ticket, Changes, Test plan, Checklist |
| `epic-default` | `/create-ticket` | Goal, Scope, Children, Success criteria |
| `story-default` | `/create-ticket` | User story, Acceptance criteria, Notes |
| `task-default` | `/create-ticket` | Description, Definition of done, Notes |

Resolution rule: a template value matching a built-in name uses the plugin's
template; any other value is resolved as a **file path** —
`<repo>/.acs/templates/<value>.md` first, then as an absolute path. Custom
templates may use the same placeholder vocabulary.

### Tracker mapping

- **GitHub** (`tracker.github`): `{ "owner": "<org-or-user>",
  "project_number": <n> }` — a GitHub Projects (v2) board. Tickets are
  created as issues in the consumer repo and added to the project; the
  ticket **type** maps to a `Type` single-select field (`Epic`/`Story`/
  `Task`, set when the board defines one — acs does not create it) and
  **status** maps to the project's `Status` field.

### Subagent models

Each Reflection role can run on its own model **and reasoning effort**,
configured under `models`:

```json
"models": {
  "executor": "sonnet",
  "verifier": { "model": "opus", "effort": "max" },
  "overrides": {
    "code": { "executor": { "model": "opus", "effort": "high" } }
  }
}
```

- A role value is either a **model string** (shorthand) or an object with
  optional `model` and `effort` keys.
- `effort` sets the reasoning effort for that subagent, passed through at
  spawn. It MUST be one of `low`, `medium`, `high`, `xhigh`, `max`, or
  `inherit` — a closed set validated fail-closed at config time, independent
  of what the chosen model supports. Any other value is a settings error, not
  a late spawn-time failure.
- Resolution is **per field** — `model` and `effort` resolve independently:
  `models.<skill>.<role>` → **inherit** (the model/effort of the
  session/parent context). So an entry can raise just the effort without
  changing the model.
- Model values are Claude model aliases or full model ids, passed through to
  the subagent spawn. The literal `"inherit"` (or omitting a key) uses the
  parent's value.
- `models.<skill>` accepts only a skill that ships subagents, and
  `models.<skill>.<role>` only a role it ships. An unknown skill or role (`ship`,
  say, which spawns none of its own) is a settings error that lists the valid ones.
- Effort has no per-call form, so an entry that sets a value is applied through a
  generated agent, `.claude/agents/acs-<skill>-<role>.md`, that `acs step start`
  keeps in step with the settings and the coordinator spawns by the name in
  `context.agents` (ADR 0115).
- Model choice is team-shareable (committed `settings.json`) and can be
  overridden per scope like any other key. acs records no token usage, so its
  effect on spend is read where Claude Code reports it
  ([ADR 0104](../../adr/0104-no-usage-dashboards-no-usage-recording.md)).

## Validation rules

- `/setup` derives the workspace (`<main-checkout>/.acs/state-machine`) —
  no key sets it — and MUST hard-fail with a `GateError` when the layout
  cannot resolve a normal main-checkout root (bare repo, submodule): acs must
  be run from a regular git checkout.
- `/setup` SHOULD create the workspace folder if missing and verify it is
  writable.
- No settings file is required: with none, every key resolves to its
  default and every pre-hook runs. A pre-hook MUST fail clearly if the
  workspace cannot be derived.
- `tests.coverage` MUST be a number in `(0, 100]`; absent → `90`.
- `ticket_prefix` is optional (absent → `ACS`, otherwise set by hand)
  and MUST be a non-empty uppercase identifier — ticket ids are
  `<prefix>-<n>`, scoped per repo. A malformed one is refused (exit 2) with
  a message to fix it in `.acs/settings.json` or remove it to use the
  default.
- A branch name is `<type>/<ticket_id>-<slug>` — ticket detection from the
  branch name depends on it, so it is fixed rather than configurable.
- `models.<skill>.<role>` MUST name a skill and a role the plugin ships, and
  carry only `model` and `effort`; an unknown model id, or an effort level the
  chosen model does not support, fails at subagent spawn with a clear error — no
  silent fallback.

## Example

The workspace always derives to `<main-checkout>/.acs/state-machine`
(ADR-0086), and documents are found rather than configured (ADR-0102): no
`settings.local.json` entry is needed at all. The example spells keys out for
illustration; a file `/setup` writes holds only the ticket prefix and the CI
gate values that differ from their defaults, and the rest below, `ticket_prefix`
included, is added by hand.

`<repo>/.acs/settings.json` (committed, team-shared):

```json
{
  "tests": {
    "coverage": 90,
    "unit": { "command": "python3 -m coverage run -m unittest discover -s tests && python3 -m coverage report --fail-under=$ACS_COVERAGE" }
  },
  "merge_strategy": "squash",
  "ticket_prefix": "SHOP",
  "models": {
    "code": {
      "implementer": { "model": "claude-sonnet-5-5", "effort": "medium" }
    },
    "review-code": {
      "lens": { "model": "claude-sonnet-5-5", "effort": "high" },
      "adjudicator": { "model": "claude-opus-5-5", "effort": "xhigh" }
    }
  },
  "tracker": {
    "provider": "github",
    "github": {
      "owner": "acme",
      "project_number": 7
    }
  }
}
```
