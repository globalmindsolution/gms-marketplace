---
name: setup
description: Optionally configure acs for the current repo — keep or change the branch/commit/PR conventions, and install the CI that enforces them. Use when setting up acs on a new repo, when changing an acs convention format, or when the user wants acs conventions enforced in CI or the pipeline protected from being bypassed.
---

You are the coordinator of `/acs:setup`, the acs bootstrap skill. This is NOT a
hooked pipeline skill: no `acs step start`, no pre/post hooks, no subagents, no
reflection loop.

**Setup is optional** (ADR-0105). acs works with its defaults before setup ever
runs: no settings file is required, and tickets take the default prefix `ACS`
(`ACS-1`, `ACS-2`, …). No other skill needs setup first.

Setup configures two things: **conventions** (the branch/commit/PR formats)
and the **CI** that enforces them. Nothing else. Every other setting has a
working default, and no setting locates a document or the workspace
(ADR-0102). A user who wants to change one — ticket prefix, tracker, models,
merge strategy, coverage target, test suites — edits `.acs/settings.json`
against `${CLAUDE_PLUGIN_ROOT}/schemas/settings.schema.json`; setup does not
ask about them. A repo that wants its own prefix sets `ticket_prefix` there by
hand (uppercase letters and digits: `SHOP` → `SHOP-123`).

**Your job is the conversation.** Every write — the settings, the ignore
entries, the workspace, the CI copies — is performed by the two commands below.
You ask, you explain the trade-off, you record the answer; you never hand-write
a `.gitignore` line or a JSON dict. Settings go to the project file
`.acs/settings.json` (committed: conventions are the team's). Unknown keys in an
existing file are legal and preserved, and a value equal to its default is never
written.

## Step 1 — Look before you ask

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" setup detect
```

Read the JSON: the settings already in the project file (`scopes`), the
resolved `workspace`, whether the ignore entries are in place (`ignored`) and
whether a broad rule is swallowing files CI must read
(`swallowed_by_a_broad_rule`), the `toolchain` and `missing_tools`, plausible
test commands (`test_command_candidates`), which CI installs are already
present (`ci`), retired settings keys still sitting in a settings file
(`retired_keys`), and the git facts. No git repository → STOP. `missing_tools`
non-empty → name each gap and its install hint now; nothing here blocks on it.

**`retired_keys` non-empty** → name each key and the file it is in, and say it
is ignored.

**A project settings file or an installed CI gate means this is a re-run** —
`scopes.project.exists` is true, or any `ci` entry has its `workflow` or
`files` present. Say so, show what is configured, and ask only about what the
user wants to change — re-running is safe by construction, and is how a repo
initialised by an older acs gets its missing ignore entries and refreshed CI
files.

## Step 2 — Ask

Use AskUserQuestion, in this order.

1. **Conventions** — show the three formats with their built-in defaults and
   ask whether to keep them:

   | Format | Default | Example |
   |---|---|---|
   | `formats.branch_name` | `{type}/{ticket_id}-{slug}` | `task/ACS-12-add-wishlist` |
   | `formats.commit_message` | `{ticket_id} {summary}` | `ACS-12 Add the wishlist endpoint` |
   | `formats.pr_title` | `{title}` | `Add wishlist support` |

   Keeping a default writes nothing. A custom format uses the placeholders
   `{ticket_id}`, `{type}`, `{slug}`, `{summary}`, `{title}`, `{ticket_ref}` and
   `{external_key}`; `branch_name` must embed `{ticket_id}`, because every acs
   skill finds the current ticket from the branch name. The default PR title
   carries no ticket id — the PR description's Ticket section links the
   ticket; a team that wants the id in titles adds `{ticket_id}` or
   `{ticket_ref}`. In `pr_title`, `{ticket_ref}` renders the tracker's native
   reference when the ticket is synced and the local id when unsynced;
   `branch_name` and `commit_message` stay id-based and unconditional in every
   case.
2. **CI enforcement** — offered explicitly, never installed silently:

   | Offer | What declining costs |
   |---|---|
   | **Convention check** (`conventions`) | branch/PR/commit conventions stay advisory; a hand-made PR can bypass the pipeline. Required check: `Branch / PR / commit conventions`. By default it checks the branch name, PR title, PR description sections and the `ACS` label; the commit-message check is off under squash merges — ask whether to turn it on (`enforcement.checks.commit_message: true`). |
   | **Tests + coverage gate** (`tests`) | the suite and the coverage target are not enforced on PRs. Needs `tests.command` — lead with `test_command_candidates` — which must run the suite and fail below `$ACS_COVERAGE` (the coverage target, default 90). Required check: `Tests & coverage`. |
   | **e2e merge gate** (`e2e`) — offered only when `e2e`/`suites.e2e` is already configured | e2e failures do not block a merge. Required check: `E2E suite`. |

## Step 3 — Apply

Write the answers to a file and run one command:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" setup apply --answers answers.json
```

The answers document carries only what the user chose — `settings` and `ci`
(any of `conventions`, `tests`, `e2e`):

```json
{"settings": {"tests": {"command": "python3 -m pytest -q --cov --cov-fail-under=$ACS_COVERAGE"}},
 "ci": ["conventions", "tests"]}
```

`--dry-run` reports what would change and writes nothing.

**Read the result.** `changed` vs `unchanged` is the point: on a re-run most
lines land in `unchanged`, which is how you show the run was safe. `defaulted`
lists answers that equal the built-in default and were therefore not written (or
removed from the file, when an earlier run had written them). `warnings` is what
you relay but must not fix for them — a conflicting `!.acs/` negation, or a broad
rule swallowing `.acs/settings.json`, is their configuration to decide. `errors`
non-empty means the settings do not validate: report and stop.
`stage_for_commit` lists what to stage (never commit unless asked);
`required_check_contexts` names the checks for branch protection.

## Step 4 — Branch protection and labels (admin, one-time)

Only when a CI gate was installed. The CI workflows are **advisory** until a
required status check makes them a gate — say that plainly: without it the
workflow runs and can be ignored. Ask the wizard for the two one-time `gh`
calls, already quoted, passing every `required_check_contexts` entry `apply`
returned:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/setup_wizard.py" commands \
  --cwd . --slug <owner/repo> --branch <default-branch> --context "<each context>"
```

`protect` is one call extending one `contexts` array; `labels` creates `ACS`
and `acs-exempt` and is harmless when they exist. Do not hand-write either:
a bare `<slug>` in a bash block is parsed as a redirection, and a context like
`Tests & coverage` backgrounds the shell at the `&`.

The judgement left to you:

- **admin = true AND consent.** Detect admin rights
  (`gh api "repos/$slug" --jq .permissions.admin`); detection alone is not
  permission, so make the mutating PUT only when the user says yes. Without
  admin, print the command **once** for an admin to run and move on:
  `/acs:setup` must never hard-fail over branch protection.
- **Register the check first.** A context GitHub has never seen returns 422:
  open a PR (or re-run the workflow) once so the check registers, then re-run.
- **`gh` auth only.** Nothing is ever stored in settings for this.

Then name the two linkage conventions reconciliation relies on, so a
hand-edited issue or PR does not break it: every synced issue body carries an
`acs-ticket: <id>` line, and every PR body a `Closes #<n>` reference. Both are
written for you; neither survives being deleted by hand.

## Step 5 — Summary and next steps

Print a table of every convention setting, its value, and where it landed
(`.acs/settings.json`, or "default — not written"). The next steps come from `commands` above —
`next_steps` carries the greenfield/brownfield call, the ordered pipeline and
the solo-maintainer caveat, so you report them rather than re-deriving them.

Repeat any unmet toolchain install hint, and confirm the workflow is ready:
Design is `/acs:create-prd` → `/acs:create-architecture` → `/acs:project` →
`/acs:create-ticket`, then `/acs:create-design` → `/acs:code` is not one fixed
chain: `/acs:create-design` runs only for a ticket flagged `needs_design`, and
the Build/Test/Ship order is declared in `workflows/ship.yaml` (`acs.py
workflow show` prints it) and walked by `/acs:ship <ticket-id>` to the PR, then
`/acs:merge-pr <id>`.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed,
interrupted, or handed off — ends your final message with the standard block
(INTERNALS.md "Completion report"). Same labels, same order, `none` where
empty; replace the Ticket line with **Repo** (no ticket at init time):

```markdown
## /acs:setup · <status>

- **Repo**: <repo> (<greenfield|brownfield>)
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: toolchain preflight outcome (tools present / still missing with the install hint); conventions written, per key (or "defaults"); retired keys found (none / named, ignored); workspace created/verified; CI convention enforcement outcome (installed / refreshed / declined), tests gate outcome, e2e gate outcome (skipped — e2e not configured / installed / declined), labels, branch protection (configured / printed-for-admin / declined)
- **Findings**: <open findings, or "none">
- **Artifacts**: <files written or staged>
- **Metrics**: <wall time>
- **Next**: brownfield: `/acs:create-prd` then `/acs:create-architecture`; greenfield: same plus `/acs:project`; then `/acs:ship <prompt>` or `/acs:create-ticket <prompt>`
```
