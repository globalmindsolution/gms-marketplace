# /acs:create-pr — committing and publishing (the Inline apply flow's charter)

Open this when the pre-hook has passed and you start the Inline apply flow in
SKILL.md, and follow it yourself. /acs:create-pr spawns no subagent: committing
a confirmed plan, pushing a branch and opening a PR is a fixed sequence of
commands with nothing for a separate agent to judge, so the coordinator runs it
inline. This skill is the ONLY place in acs that creates a branch, stages,
commits or pushes (ADR-0127): every step before it leaves its output as
uncommitted changes in the working tree and records the paths it wrote. Here
those changes become the commits the user confirmed, on a new branch, then the
branch is pushed, the PR body rendered from the template, the `ACS` label
ensured, the pull request created or updated against the default branch, the
PR reference recorded, and the tracker synced when configured. Where reality
turns out to contradict the state files, do the closest faithful thing and
record the deviation in the publish report — never improvise a different flow.

**Where the cross-references below point.** Step numbers are the Inline apply
flow's in SKILL.md, which states each step in full; this file holds what binds
them together — the order, the rules each one must not break, and the report
the run leaves behind. Resuming is `references/resume.md`; reading a red
ticket-link check is
`${CLAUDE_PLUGIN_ROOT}/skills/create-pr/references/ci-convention-check.md`.

## What you work from

READ EVERY ONE of these before acting — workspace state, never conversation
history:

- the run's `requirements.md` (`context.requirements.path`) — the
  acceptance criteria whatever container they came from — and the ticket's
  `ticket.json`, when the run has a ticket — title, type, `external`;
- `steps/code/state.json`, `specs/*.md`, and `tech-design.md` when the ticket
  has one;
- the commit plan `acs.py pr plan-commits` printed, and the confirmed copy you
  write to `steps/create-pr/iter-<n>/commit-plan.json` (through `acs.py write`);
- the resolved body template file;
- the values you settle along the way: the PR title, the
  `base_branch`, the `branch` the plan names, the commits made, and
  `tracker_provider`.

## GitHub call failure policy, as it applies here

Canon lives in `create-pr/SKILL.md`'s own "GitHub call failure policy"
section — this reference classifies no GitHub call
itself, it only follows that classification (critical for branch/base
detection and PR create/edit; non-critical for the metadata/tracker-fill
calls). Canon hint text (`acs_lib.GH_ACCESS_HINT`, selected by
`acs_lib.gh_failure_hint(stderr)`):

> This looks like a session-level access restriction — a Claude Code
> cloud/managed session must have the Claude GitHub App connected for this
> organization by an org admin. A local Claude Code session uses your own
> `gh` authentication and should not see this.

## Commit the confirmed plan, in this order

The commit phase is local: it calls no `gh` and touches no remote.

C1. **Plan.** `acs.py pr plan-commits --out …` plans for the run, whatever its
   subject — a ticket, a prompt, or (a prompt with no current run) a new
   prompt-subject run whose changeset is every uncommitted change against
   HEAD. Its groups are ordered layer by layer — documents first, one group
   per doc set (the change's Development docs
   `<development_dir>/<feature>/<ID>/`, the PRD and its features' analyses,
   `hld/`, each `lld/<feature>/` with its design records, ADRs, and a legacy
   `docs/tickets/<ID>/` a run still touched), then per plan slice or file-map partition its
   tests and then its code (one commit when a slice has only one kind; a run
   with no plan: tests, then code), then docs-sync's doc updates, then the e2e
   suites. In a run whose steps recorded their files, a path is in a group
   only when a step recorded it AND it changed since the run's baseline;
   other runs' recorded `states.files` refine the grouping where they name a
   changed path. `left_out` is what changed but no step recorded; `excluded`
   is what was already dirty when the run began. The CLI is the plan's only author: never assemble one
   from `git status`, and never fold `left_out` or `excluded` into a group on
   your own.
C2. **Preview and confirm.** One grouped AskUserQuestion — confirm / edit /
   cancel — showing the branch, every group (subject and paths, in commit
   order), `left_out` and `excluded`. The edits are the user's and only the
   user's: move a path between groups, drop a path from a group, add a
   `left_out` path to a group, reword a subject (keeping the configured
   commit-subject format — the ticket id leads it only when there is a
   ticket). An `excluded` path is never added. After an edit,
   show the edited plan once more; a run that cannot reach the user and holds
   no approval of the plan in the request commits nothing (`needs_input`).
C3. **Keep** the confirmed plan in `steps/create-pr/iter-<n>/commit-plan.json`
   (C1's `--out` wrote it as proposed; rewrite it only after an edit).
C4. **Commit** with `acs.py pr commit --plan steps/create-pr/iter-<n>/commit-plan.json`:
   it switches to the plan's branch (creating it from the current checkout,
   which carries the working tree along) and commits the groups in order, each
   by pathspec, printing every commit's sha and what `remaining` stays
   uncommitted. Its refusals — the default branch, a branch that exists at
   another commit, a path that is not an uncommitted change, a path in two
   groups, an empty group — end the run failed; they are never routed around
   with raw git.

## Ship the PR, in this order

1. **Branch and base.** The branch is the one C4 committed to (or, with no
   groups to commit, the one C1 named — it must exist locally:
   `git rev-parse --verify <branch>`). Detect the base BEFORE anything is
   pushed — `gh api repos/{owner}/{repo} --jq .default_branch`.
   The base detect, step 3's label create and step 5's
   open-PR detect depend on nothing but the branch name: issue them as parallel
   Bash calls in ONE message (SKILL.md step 1) and reuse their answers.
   Then push: `git push -u origin <branch>`; skip the push when the branch is
   already on origin and current. A failed critical call stops the run before
   the push; the commits stay on the local branch for the re-run.
2. **Body.** Fill the resolved template into
   `steps/create-pr/pr-body.md` through `acs.py write` (SKILL.md, Finish): replace every placeholder
   (`{ticket_id}`, `{type}`, `{title}`, `{summary}`, `{external_key}`;
   `{external_key_line}` renders as ` — tracker: <provider> <key>` when
   `ticket.external` is set, empty otherwise); replace the template's HTML comments
   with real content and DELETE the comments; fill every section strictly from the
   state files and the commits made — the Changes section lists every commit
   (short sha, subject, paths) in order. Checklist items are `[x]` ONLY when
   code-state substantiates them (e.g. review loop passed only when
   `review.findings_open == 0`) — an unearned tick is a lie the reviewer of the
   PR will catch. Write the title directly (concise, normally the ticket's
   title) and pass it verbatim.
3. **Label.** Ensure the label exists, then rely on it at create/edit time:
   `gh label create ACS --description "Created by the acs pipeline" 2>/dev/null || true`
   — a run with no ticket ensures and applies `acs-exempt` too: its PR names no
   ticket, and the installed CI check (`templates/ci/acs-conventions.yml`)
   fails any PR that names none unless that label exempts it.
4. **Pre-open self-check.** `pr-conventions.py check` on the filled body, with
   its bounded re-fill retry (SKILL.md step 4) — a deterministic call, not a
   subagent. A body that still fails is never opened.
5. **Create or update.** Follow the branch's state
   (`rest-transport.md`, "Detect"):
   - No open PR for the branch: create it with the REST call in
     `rest-transport.md` (title verbatim, body from `pr-body.md`, label `ACS`;
     no ticket: plus `acs-exempt`) — no draft; PRs ship ready-for-review.
   - An open PR already exists: update it with the REST calls there (title,
     body, `ACS` label, base when wrong, ready-for-review when a draft).
6. **Record.** The REST create/update response (`rest-transport.md`) — capture `{number, url, branch, base}` into the publish report and, at
   Finish, into `states.pr` for the /acs:merge-pr gate; never report a PR you
   did not confirm live.
6a. **Tracker-metadata fill (github-tracker only)** — only when
   `tracker_provider == "github"` AND `ticket.external.key` is set (the same
   guard step 7 below uses); applies on **both** the create and edit paths of
   step 5, now that the PR number is known from step 6. One command:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" pr metadata fill \
     --pr <number> [--author <login>]
   ```

   `--author` is OPTIONAL and exists only so the author is dropped from their
   own reviewer set; omit it and the command resolves the login itself with
   `gh api user`. Any spelling works — `alice`, `@alice`, `@me`, `Alice` — the
   comparison is `@`-stripped and case-folded on both sides.

   It assigns the PR, applies the ticket-type label alongside `ACS`, requests
   the CODEOWNERS-derived reviewers with the author dropped, adds the PR to the
   Project, and sets Status and the Priority / Story Points / Parent fields the
   board defines. When the guard does not hold it reports `skipped: true` and
   writes nothing.

   **Non-critical throughout**: exit 0 means the pass ran, not that every field
   landed. Copy the printed `findings` into the publish report's
   `metadata_fill.findings` verbatim — each is an `info` finding carrying the
   command, ready to re-run — and never fail the PR over one.

7. **Tracker sync** — only when `tracker_provider` is `github` AND
   `ticket.external.key` is set (skip for `local`; when the provider is configured
   but the ticket was never synced, record an info finding instead):
   - `github`: `gh issue comment <external.key> --body "ACS: PR #<number> opened for <ticket-id> — <url>"`

On a resumed run (`references/resume.md`), redo exactly what the reconcile
found unfinished — finish the confirmed plan from its first uncommitted group,
re-write the title, re-fill the body, re-push, re-label, fix the base,
whatever it names — and nothing else beyond what that requires.

## The publish report

Write `steps/create-pr/iter-<n>/publish.json` (`<n>` = the run's iteration,
normally 1) through `acs.py write`, never the Write tool:

```json
{
  "artifacts": ["steps/create-pr/iter-1/commit-plan.json", "steps/create-pr/pr-body.md"],
  "run_mode": "ticket",
  "commit_plan": {"path": "steps/create-pr/iter-1/commit-plan.json", "confirmed_by": "C-1", "left_out": ["notes/todo.md"], "excluded": []},
  "commits": [{"id": "ticket-docs", "sha": "0f3c2ab9", "subject": "SHOP-123 Add ticket docs", "paths": ["docs/development/bulk-import/SHOP-123/analysis.md"]},
              {"id": "slice-01-tests", "sha": "5d1e07c4", "subject": "SHOP-123 Add tests for bulk import", "paths": ["tests/test_import.py"]},
              {"id": "slice-01-code", "sha": "9a8b7c6d", "subject": "SHOP-123 Implement bulk import", "paths": ["src/shop/importer.py"]}],
  "pr": {"number": 42, "url": "https://github.com/acme/shop/pull/42", "branch": "task/SHOP-123-bulk-import", "base": "main"},
  "pushed_sha": "9a8b7c6d",
  "mode": "created",
  "commands_run": [{"cmd": "python3 .../acs.py pr commit --plan steps/create-pr/iter-1/commit-plan.json", "outcome": "3 commits on task/SHOP-123-bulk-import"},
                   {"cmd": "git push -u origin task/SHOP-123-bulk-import", "outcome": "pushed 9a8b7c6d"}],
  "self_check": {"passed": true, "attempts": 1},
  "tracker_sync": {"provider": "github", "key": "acme/shop#88", "result": "comment posted"},
  "metadata_fill": {"assignee": "added @me", "type_label": "task", "project": {"added": true, "status_set": true}, "reviewers": {"requested": ["@alice", "@org/team-frontend"], "skipped_reason": null, "findings": []}, "project_fields": {"priority": "High", "story_points": 3, "parent": "#42", "findings": []}, "findings": []},
  "problems": [], "clarifications_used": []
}
```

How the run ends, and what the report then says:

- **completed** — the confirmed plan committed, branch pushed, PR live with
  title/body/label, commits and reference recorded in the publish report and
  in `states.commits` / `states.pr`.
- **needs user input** — the commit plan awaits the user's confirmation in a
  run that cannot ask, or reality blocks you (the branch carries commits the
  plan does not account for, foreign open PR with conflicting base): ask
  exactly what you need (SKILL.md's User interaction); nothing is committed
  without a confirmed plan, and the report lists whatever you safely produced.
- **cancelled** — the user cancelled at the preview: nothing committed or
  pushed; the result is `interrupted` / `needs_input`.
- **failed** — the plan or the commit refused, or push or PR creation
  impossible (auth, protections, network): the report's `problems` and the
  result document's `errors` say why; report partial state honestly —
  commits already made are recorded, never undone.

## Hard rules

- Spawn no subagent for any of this: the steps above are ordered commands the
  coordinator runs itself.
- Mutate ONLY what this flow covers: the branch and commits `acs.py pr commit`
  makes from the confirmed plan, the push of that branch, the PR itself
  (create/edit/ready/label), the `ACS` (and, with no ticket, `acs-exempt`) label,
  the tracker comment, plus `commit-plan.json`, `pr-body.md` and the publish
  report under `steps/create-pr/`, then the result document and the post-hook
  at Finish. Do not merge, do not delete branches, do not edit `ticket.json`,
  `steps/code/state.json`, `run.json`, or any other workspace state — the
  post-hook owns what changes after the PR exists.
- Commit ONLY through `acs.py pr commit --plan` and ONLY what the user
  confirmed: never `git add -A`, `git add .`, `git commit -a` or any raw
  `git add` / `git commit`; never commit to the default branch; never include
  a `left_out` path the user did not move into a group, or an `excluded` one
  at all. Never stash, reset, restore, clean or check out over the user's
  work — what the plan leaves out stays in the working tree exactly as it
  was.
- Never fabricate body content: every Summary/Changes/Test-plan claim comes from
  `requirements.md`, `ticket.json`, `specs/`, `tech-design.md`, `steps/code/state.json`, or the commits
  `acs.py pr commit` printed (with no ticket: the run's requirements and the changed
  files) — a section the
  state cannot fill stays honest and minimal.
- If `git push` or the PR create call fails, capture the exact stderr plus the
  canonical hint from `acs_lib.gh_failure_hint` in the report's `problems` and
  the result document's `errors` (critical, per create-pr/SKILL.md's
  classification); never retry
  destructively (no force-push, ever), and never undo a commit already made.

## Grounding (anti-hallucination)

Every decision, claim, and finding you record must be traceable to a source
you actually read or ran in THIS run:

- **Cite the source next to the statement it supports** in the publish report
  and the PR body: file path with line numbers or section heading for anything
  based on repo code, docs, the ticket, specs, design, or workspace state.
- **Quote the exact command and the relevant output** for anything based on a
  command run (tests, builds, coverage, git/gh state).
- **Never assert what you did not observe**: the content of a file you did not
  open, a PR you did not confirm live, a test result you did not see. If an
  input is missing or unreadable, record it in `problems` instead of working
  from an assumed version.
- **Mark unverifiable points as assumptions**, with the reason the assumption
  is needed — an assumption is a finding to resolve with the user, never a
  silent default baked into the PR.
