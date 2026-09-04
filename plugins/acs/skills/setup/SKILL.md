---
name: setup
description: Initialize or update the acs configuration for the current repo — settings scope, workspace path, ticket prefix, coverage target, merge strategy, tracker, doc paths, formats, subagent models, and optional CI enforcement of PR/branch/commit conventions. Use when setting up acs on a new repo, when another acs skill fails with "run /acs:setup first", when the user wants to enforce acs conventions in CI or stop the pipeline being bypassed, or when changing any acs setting.
---

You are the coordinator of `/acs:setup`, the acs bootstrap skill. This is NOT a
hooked pipeline skill: no `skill-start.py`, no pre/post hooks, no subagents, no
reflection loop. Every other acs skill's pre-hook fails with "run /acs:setup
first" until this skill has produced a valid configuration.

**Your job is the conversation.** Every write — the settings split across
scopes, the ignore entries, the workspace, the CI copies, the `CLAUDE.md` block,
the status-line settings — is performed by the two commands below (MAR-526). You
ask, you explain the trade-off, you record the answer; you never hand-write a
`.gitignore` line or a JSON dict. Settings MUST conform to
`${CLAUDE_PLUGIN_ROOT}/schemas/settings.schema.json`; unknown keys in existing
files are legal and preserved, because every write is a read-update-write merge.

## Step 1 — Look before you ask

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" setup detect
```

Read the JSON: which settings exist and **in which scope** (`scopes`), the
resolved `workspace`, whether the ignore entries are in place (`ignored`) and
whether a broad rule is swallowing files CI must read
(`swallowed_by_a_broad_rule`), the `toolchain` and `missing_tools`, plausible
test commands (`test_command_candidates`), which optional installs are already
present (`ci`, `claude_md`, `status_line`), and the git facts. No git repository
→ STOP. `missing_tools` non-empty → name each gap and its install hint now;
nothing here blocks on it.

**Existing settings in `scopes` means this is a re-run.** Say so, show what is
configured, and ask only about what the user wants to change — re-running is
safe by construction, and is how a repo initialised by an older acs gets its
missing ignore entries and refreshed CI files.

## Step 2 — Ask

Use AskUserQuestion. Ask in this order, and never write a setting the user did
not choose — a default the user did not pick is a default, not a value to record.

1. **Scope** — `project` (`<repo>/.acs/settings.json`, committed, the team's
   choice) or `user` (`~/.acs/settings.json`, yours alone). Machine-specific
   keys always go to the gitignored `settings.local.json` regardless.
2. **`ticket_prefix`** — required, no default. Suggest one from the repo name
   (`acme-shop` → `SHOP`). Uppercase letters and digits, e.g. `SHOP-123`.
3. **The optional settings** — see the batch below.
4. **The opt-ins**, each offered explicitly and never written silently:

   | Offer | Default | What declining costs |
   |---|---|---|
   | **Status line** (`statusLine` + `subagentStatusLine`) | ask | acs samples real cost figures from the statusLine payload (ADR 0080): without it every run's cost renders `unavailable`. Token counts still render `measured` — those come from the transcript. Never overwrites an existing value. |
   | **CI convention enforcement** | ask | branch/PR/commit conventions stay advisory; a hand-made PR can bypass the pipeline. Required check: `Branch / PR / commit conventions`. |
   | **CI tests + coverage gate** | ask | the suite and the coverage target are not enforced on PRs. Required check: `Tests & coverage`. |
   | **e2e required merge gate** | ask, only when `e2e`/`suites.e2e` is configured | e2e failures do not block a merge. Required check: `E2E suite`. |
   | **`CLAUDE.md` guidance block** | **yes** | every Claude session in the repo may freelance a raw `gh pr create`, and a non-ticket PR has no ticket for `/acs:merge-pr` to resolve. Rendered from `templates/CLAUDE.acs.md` and written with `upsert_managed_block`, so it is marker-delimited and a re-run replaces only that span. |

### Optional settings

| Key | Default | Consumed by |
|---|---|---|
| `workspace_path` | `<repo>/.acs/state-machine` (in-repo, gitignored) | every skill; always written to `settings.local.json` |
| `test_coverage_percent` | `90` | `/acs:code`'s coverage hard fail, the CI tests gate |
| `merge_strategy` | `squash` | `/acs:merge-pr` |
| `prd_path` | `docs/product` | `/acs:create-prd` |
| `architecture_path` | `docs/architecture` | `/acs:create-architecture` |
| `adr_path` | `docs/adr` | `/acs:create-architecture` |
| `quality_path` | `docs/quality` | `/acs:create-quality` |
| `operations_path` | `docs/operations` | `/acs:create-operations` |
| `principles_path` | `docs/principles` | `/acs:create-principles` |
| `standards_path` | `docs/standards` | `/acs:create-standards` |
| `suites` | `{}` | `/acs:test` runs each named suite; the reserved name `e2e` is auto-populated from the `e2e` key below — never hand-duplicate it |
| `tracker` | `{"provider": "local"}` | `/acs:create-ticket`, `/acs:create-pr`; `github`/`jira` need their own block and a working CLI (`detect`'s `toolchain`) |
| `formats` | built-ins | branch / PR title / commit naming, and the CI conventions gate. `pr_title` is provider-aware: it renders the **tracker's native reference when synced**, and the local id when unsynced. `branch_name` and `commit_message` stay id-based and unconditional in every case. |

Present these as a batch (AskUserQuestion or a compact list) with their
defaults; accept the defaults silently if the user says "defaults are fine".
Two exceptions are always asked explicitly on a fresh init, never
silently-defaulted: **`### models`** (below) AND **`e2e`** (the bullet below) —
both are first-class setup decisions, so present each as its own choice even
when the user takes the defaults for everything else.

- `e2e` — **always ask** explicitly on a fresh init; default UNSET (the repo has
  no e2e suite). Lead with what `detect` and the repo show (`package.json`
  scripts containing `e2e`, `playwright.config.*`, `cypress.config.*`, Makefile
  targets) so the offer is candidate-driven, not a blank prompt. When the user
  configures it, collect `e2e.command` (required), optional `e2e.setup`/
  `e2e.teardown`, and `e2e.per_iteration` (default `false` — e2e is slow, so the
  code-verifier then runs it only on the final, otherwise-passing iteration).
  Declining leaves it UNSET — offered, not defaulted. Configured e2e makes the
  suite part of every /acs:code verification.

  On a **re-run** where the settings already carry a configured `e2e`, offer the
  `e2e` → `suites.e2e` migration: show the current value, explain that `e2e` is
  a soft-deprecated compatibility alias and `suites.e2e` the canonical form, and
  offer to write the equivalent `suites.e2e` entry alongside the retained `e2e`
  key — leave `e2e` in place unless the user explicitly opts to remove it.
  Declining leaves settings unchanged; the offer was made, not forced.

### models

**On a fresh init, ALWAYS ask this** — model choice is a first-class setup
decision. Offer three shapes with AskUserQuestion:

1. **Recommended (default)** — the version-pinned ids, never the coarse tier
   aliases: `planner: claude-opus-5`, `executor: claude-sonnet-5`,
   `verifier: claude-opus-5` (opus for strong reasoning on planning and review,
   the faster/cheaper sonnet for the mechanical execution role). Pinned ids
   (MAR-81) land a fresh init on a stable, explicit model rather than a runtime
   alias. Pick this and move on if unsure — a repo that wants a stronger
   execution role takes **Custom**.
2. **Inherit the session model** — set nothing; every role runs on whatever the
   user's Claude Code session is using.
3. **Custom** — set any of the three roles individually.

**Reasoning effort per role** is its own choice, not merely the object-shape
note: for every role the user pins, offer a level —
`low | medium | high | xhigh | max | inherit` (`inherit` leaves it to the
model's default). The pinned default sets `high` for planner/executor/verifier.

On a **re-run**, show the currently-resolved per-role models and where each came
from, and ask only whether to change them — never force a re-pick.

Shape per role (`planner`, `executor`, `verifier`): a model string, or
`{"model": "...", "effort": "..."}`, plus per-skill
`models.overrides.<skill>.<role>`. Any non-empty model string is accepted (so a
newer model name works without a skill update); resolution is per field:
override → role → inherit. Write `models` only for Recommended or Custom; for
Inherit omit it entirely, which is the schema default.


## Step 3 — Apply

Write the answers to a file and run one command:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" setup apply --answers answers.json
```

The answers document carries only what the user chose — `settings` (to the
chosen scope), `workspace_path` (always to the gitignored
`settings.local.json`), `ci` (any of `conventions`, `tests`, `e2e`),
`claude_md`, and `status_line`:

```json
{"scope": "project", "settings": {"ticket_prefix": "SHOP"},
 "ci": ["conventions", "tests"], "claude_md": true,
 "status_line": {"scope": "user", "statusLine": true, "subagentStatusLine": true}}
```

`--dry-run` reports what would change and writes nothing.

**Read the result.** `changed` vs `unchanged` is the point: on a re-run most
lines land in `unchanged`, which is how you show the run was safe. `warnings` is
what you relay but must not fix for them — a conflicting `!.acs/` negation, or a
broad rule swallowing `.acs/settings.json`, is their configuration to decide.
`errors` non-empty means the settings do not validate: report and stop.
`stage_for_commit` lists what to stage (never commit unless asked);
`required_check_contexts` names the checks for branch protection.

## Step 4 — Branch protection (admin, one-time)

The CI workflows are **advisory** until a required status check makes them a
gate — say that plainly: without it the workflow runs and can be ignored.
Detect admin rights (`gh api repos/<slug> --jq .permissions.admin`); with them,
offer to configure protection yourself; without them, print this for an admin to
run once, with every `required_check_contexts` entry in one `contexts` array:

```bash
gh api -X PUT repos/<slug>/branches/<branch>/protection \
  -f "required_status_checks[strict]=true" \
  -f "required_status_checks[contexts][]=<context>" ...
```

Rules for this step, all of them user-facing:

- **One call, one array.** Every context — `Branch / PR / commit conventions`,
  `Tests & coverage`, `"E2E suite"` — extends the **same** `contexts` array;
  never a second protection call per gate. The e2e context is added only when
  `e2e`/`suites.e2e` is configured; unset means the whole offer is a no-op.
- **admin = true AND consent.** Admin detection alone is not permission: make
  the mutating PUT only when the user says yes.
- **Register the check first.** A context GitHub has never seen returns 422
  (unknown context): open a PR (or re-run the workflow) once so the check
  registers, then re-run the protection call.
- **Print it once, never hard-fail.** Without admin, print the command once for
  an admin to run and move on; `/acs:setup` never fails over branch protection.
- **`gh` auth only.** Nothing is ever stored in settings for this: `gh` is the
  transport and its own authentication is what authorises the call.

## Step 5 — Labels and the tracker conventions

When the tracker is `github` (or the repo has a GitHub remote), ensure the two
labels the pipeline uses. Best-effort, harmless when they exist:

```bash
gh label create ACS        --description "Created/validated by the acs pipeline" 2>/dev/null || true
gh label create acs-exempt --description "Skip acs convention checks for this PR" 2>/dev/null || true
```

Name the two linkage conventions reconciliation relies on, so a hand-edited
issue or PR does not break it: every synced issue body carries an
`acs-ticket: <id>` line, and every PR body a `Closes #<n>` reference. Both are
written for you; neither survives being deleted by hand.

## Step 6 — Summary and next steps

Print a table of every resolved setting, its value, and where it landed (or
"default — not written"), then the next steps. `git ls-files` decides greenfield
vs brownfield — an existing product codebase is brownfield, an empty or
docs-only repo greenfield:

- **Brownfield**: `/acs:create-prd`, then `/acs:create-architecture`, merging
  each PR with `/acs:merge-pr <ticket-id>` after review. On a solo-maintainer
  repo that skill cannot merge (it requires an APPROVED review and GitHub
  forbids self-approval) — merge in the GitHub UI instead.
- **Greenfield**: the same two, plus `/acs:create-project` to scaffold.
- Then `/acs:ship <prompt>`, or step by step from `/acs:create-ticket <prompt>`.

Repeat any unmet toolchain install hint so the gap stays explicit, and confirm
the workflow is ready: `/acs:setup`, then the pipeline `/acs:create-prd` →
`/acs:create-architecture` → `/acs:create-project` → `/acs:create-ticket` →
`/acs:create-design` → `/acs:code` → `/acs:test` (conditional) →
`/acs:docs-sync` → `/acs:create-pr` → `/acs:merge-pr`, the umbrella
`/acs:ship`, and `/acs:handoff`, `/acs:update`, `/acs:install-hooks`. Offer the
one-shot workspace migration when `detect` shows an external `workspace_path`
the user wants moved in-repo (`migrate_workspace.py --help`).

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"), rendered only AFTER the post-hook
succeeded. Same labels, same order, `none` where empty; replace the Ticket line with **Scope** (no ticket at init time):

```markdown
## /acs:setup · <status>

- **Scope**: <user|project> settings for <repo> (<greenfield|brownfield>)
- **Status**: <status> — <stop_reason>
- **Results**: toolchain preflight outcome (tools present / installed / still missing with the install hint); settings written, per key: value and which file (user/project `settings.json`, gitignored `settings.local.json`); workspace created/verified; tracker CLI check outcome; status line + subagent status line opt-in outcomes (configured at which scope / declined / already set); CI convention enforcement outcome (checks enabled, files written, labels, pre-push choice, branch-protection: configured / printed-for-admin / declined); e2e gate CI convention outcome (skipped — e2e not configured / files written / branch-protection: configured / printed-for-admin / declined); `CLAUDE.md` pipeline-default guidance block (written / refreshed / declined)
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files, repo paths, branch, PR URL>
- **Metrics**: <wall time> · ~<tokens in/out> · ~$<cost_usd>
- **Next**: brownfield: `/acs:create-prd` then `/acs:create-architecture`; greenfield: same plus `/acs:create-project`; then `/acs:ship <prompt>` or `/acs:create-ticket <prompt>`
```
