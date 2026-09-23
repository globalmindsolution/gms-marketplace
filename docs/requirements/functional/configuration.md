# Configuration & `/setup`

The `acs` plugin must work on **different consumer repos**. Configuration is
stored as `settings.json` under an `.acs` folder. The `/setup` skill writes
the conventions — `ticket_prefix`, the `formats.*` strings — and the settings
of the CI gates it installs; every other key has a working default and is
edited by hand, validated against `settings.schema.json`.

## Scopes & files

| Scope | Path | Git | Use |
|-------|------|-----|-----|
| User | `~/.acs/settings.json` | n/a | Defaults shared across all of a user's repos. |
| Project (shared) | `<repo>/.acs/settings.json` | **committed** | Team-shared, repo-specific settings (formats, tracker, coverage, merge strategy). |
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
| `test_coverage_percent` | number | `90` | No | Coverage target used by `/code` when generating unit tests and running them in the TDD cycle. Missing the target is a hard fail. |
| `merge_strategy` | string | `"squash"` | No | How `/merge-pr` merges: `squash` \| `merge` \| `rebase`. |
| `ticket_prefix` | string | — | **Yes — user input at setup time** | Per-repo prefix for generated ticket ids (`<prefix>-<sequence>`), e.g. `SHOP` for a shop product; `/setup` suggests one derived from the repo name. There is no global default — different consumer repos get different prefixes. The per-repo sequence counter lives in the workspace (`counters.json`). |
| `e2e` | object | unset | No | **Deprecated compatibility alias** for `suites.e2e`: `{ "command", "setup"?, "teardown"?, "per_iteration"? }`. Still accepted and validated exactly as before, but normalized at load time into `suites["e2e"]` — new configuration should prefer `suites.e2e` directly (moving an existing `e2e` key across is a hand edit). Unset = no e2e suite. When configured: spec test plans state the e2e impact, `/code` authors the declared e2e tests in the same changeset, and `/acs:review-code`'s final gate runs the full suite (`setup` → `command` → `teardown` always) — a green run is required for a passing verdict; `per_iteration: false` (default) defers the run past iterations that already have other blocking findings. `/create-project` scaffolds the harness and proposes this block for greenfield repos with a user-facing surface. This same `e2e`/`suites.e2e` configuration is also the **single opt-in signal** for the CI required merge gate — no dedicated `e2e.ci`/`suites.e2e.ci` enable key exists, or is ever introduced (see the e2e merge gate note below). |
| `suites` | object | `{}` | No | The single source of truth for named test commands: `{ "<name>": { "command", "setup"?, "teardown"?, "per_iteration"? } }`. The reserved name `e2e` is auto-populated at load from a configured `e2e` key (see above). `/acs:test` is the consumer — it runs all configured suites, or a `--suite`-selected subset, capturing pass/fail results to an auditable workspace artifact. |
| `tests` | object | unset | No | Unit/integration suite for the **CI tests + coverage gate** scaffolded by `/acs:setup` (Step 3, opt-in): `{ "command", "setup"? }`. `command` runs the suite and MUST fail on a coverage shortfall — delegate to the tool (e.g. `pytest --cov --cov-fail-under=$ACS_COVERAGE`); acs exports `ACS_COVERAGE` (= `test_coverage_percent`) into the environment. Installed as `.github/workflows/acs-tests.yml` + `.acs/ci/run-tests.py`, which read the **committed** project `.acs/settings.json` (the CI runner has no acs install). A merge gate once made a required status check (`Tests & coverage`) on a protected default branch. |

**e2e required merge gate (`/acs:setup`, opt-in).** When `e2e`/
`suites.e2e` is already configured — by hand; `/acs:setup` does not configure
a suite — `/acs:setup` offers the gate at Step 2 and Step 3 scaffolds
`.github/workflows/acs-e2e.yml` + `.acs/ci/run-e2e.py` — the same
committed-settings-reading pattern as the tests gate, independent of it (a
repo can gate on one, both, or neither). **Opt-in invariant**: when
`e2e`/`suites.e2e` is unset, the gate is never offered — no files copied, no
`gh api` call, zero new behavior. `run-e2e.py` resolves the command from
`suites["e2e"]` or the raw `e2e` alias, runs `setup` → `command` → `teardown`
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
| `models` | object | inherit | No | Which Claude model **and reasoning effort** each subagent role runs on: `models.executor`, `models.verifier` (a `models.planner` entry is still accepted but inert — no skill spawns a planner since ADR 0092), with per-skill overrides under `models.overrides.<skill>`. Each role accepts a model string or a `{ "model", "effort" }` object. See [Subagent models](#subagent-models). |
| `tracker` | object | `{ "provider": "local" }` | No | Ticket tracking backend. `provider` is `local` (default), `github` (GitHub Projects), or `jira` (Jira board). Tickets are always stored **local-first** in the workspace; when `github`/`jira` is configured, tickets sync **two-way** with the remote tracker, and `ticket.json` keeps the local↔remote id mapping. Access goes through the official CLIs: `gh` (GitHub) and `acli` (Jira). Provider-specific sub-keys live under `tracker.github` / `tracker.jira`. |
| `formats` | object | built-in defaults | No | Formats for generated artifacts. Short fields are inline template strings with placeholders such as `{ticket_id}`, `{title}`, `{type}`, `{summary}`: `formats.branch_name` (MUST embed `{ticket_id}`), `formats.commit_message`, `formats.pr_title`, and per-ticket-type titles under `formats.tickets.<type>` (`epic`, `story`, `task`). **Descriptions** (PR description, ticket descriptions) use **pre-defined templates** shipped with the plugin, referenced by name; users can select another template or point to a custom template file. |
| `evals` | object | unset | No | **Read by nothing.** Accepted by the schema and ignored: its only reader was the behavioural-eval harness's forge tier, retired when the eval suite moved to `claude plugin eval` case files. It never affected the hook layer, so it changes no acs runtime behavior. Kept in the schema so a consumer's existing settings stay valid; removing it is a schema change for its own release. `evals.forge_repo` named the forge-tier target repo (`owner/name`) and MUST NOT be a production repo. |

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
(ADR-0086). Neither has an override.

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
- **Jira** (`tracker.jira`): `{ "base_url": "<url>", "project_key": "<KEY>"
  }` — types map to Jira's standard issue types (epic → Epic, story →
  Story, task → Task); status changes use Jira transitions (In Progress,
  Done); epic↔child links use Jira's parent/epic link.

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
  `models.overrides.<skill>.<role>` → `models.<role>` → **inherit** (the
  model/effort of the session/parent context). So a per-skill override can
  raise just the effort without changing the model.
- Model values are Claude model aliases or full model ids, passed through to
  the subagent spawn. The literal `"inherit"` (or omitting a key) uses the
  parent's value.
- `models.overrides.<skill>` accepts only a skill that spawns reflection
  subagents — the hooked skills. An unknown skill name (`ship`, say, which
  spawns none of its own) is a settings error.
- Model choice is team-shareable (committed `settings.json`) and can be
  overridden per scope like any other key. Its effect on token usage is visible
  in the per-run metrics ([workspace-and-state.md](workspace-and-state.md)).

## Validation rules

- `/setup` derives the workspace (`<main-checkout>/.acs/state-machine`) —
  no key sets it — and MUST hard-fail with a `GateError` when the layout
  cannot resolve a normal main-checkout root (bare repo, submodule): acs must
  be run from a regular git checkout.
- `/setup` SHOULD create the workspace folder if missing and verify it is
  writable.
- Every pre-hook MUST fail (exit 2) with a "run /setup first" message if no
  `settings.json` can be resolved, and fail clearly if the workspace cannot
  be derived.
- `test_coverage_percent` MUST be a number in `(0, 100]`; absent → `90`.
- `ticket_prefix` is required at setup time (suggested from the repo name)
  and MUST be a non-empty uppercase identifier — ticket ids are
  `<prefix>-<n>`, scoped per repo.
- `formats.branch_name` MUST include the `{ticket_id}` placeholder — ticket
  detection from the branch name depends on it.
- `models` entries MUST be non-empty strings or `{ "model", "effort" }`
  objects; an unknown model id, or an effort level the chosen model does not
  support, fails at subagent spawn with a clear error — no silent fallback.

## Example

The workspace always derives to `<main-checkout>/.acs/state-machine`
(ADR-0086), and documents are found rather than configured (ADR-0102): no
`settings.local.json` entry is needed at all. The example spells keys out for
illustration; a file `/setup` writes holds only `ticket_prefix` and the
convention/CI values that differ from their defaults, and the rest below is
added by hand.

`<repo>/.acs/settings.json` (committed, team-shared):

```json
{
  "test_coverage_percent": 90,
  "merge_strategy": "squash",
  "ticket_prefix": "SHOP",
  "models": {
    "executor": "sonnet",
    "verifier": { "model": "opus", "effort": "max" },
    "overrides": {
      "code": { "executor": { "model": "opus", "effort": "high" } }
    }
  },
  "tracker": {
    "provider": "jira",
    "jira": {
      "base_url": "https://acme.atlassian.net",
      "project_key": "SHOP",
      "board": "SHOP board"
    }
  },
  "formats": {
    "branch_name": "{type}/{ticket_id}-{slug}",
    "commit_message": "{ticket_id} {summary}",
    "pr_title": "[{ticket_id}] {title}",
    "pr_description_template": "pr-default",
    "tickets": {
      "epic": { "title": "[EPIC] {title}", "description_template": "epic-default" },
      "story": { "title": "{title}", "description_template": "story-default" },
      "task": { "title": "{title}", "description_template": "task-default" }
    }
  }
}
```
