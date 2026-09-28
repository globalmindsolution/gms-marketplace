# /acs:create-pr — publishing the PR (the Inline apply flow's charter)

Open this when the pre-hook has passed and you start the Inline apply flow in
SKILL.md, and follow it yourself. /acs:create-pr spawns no subagent: pushing a
branch and opening a PR is a fixed sequence of commands with nothing for a
separate agent to judge, so the coordinator runs it inline. This is the ONLY
part of the skill that touches origin and GitHub: push the ticket branch,
render the PR body from the template, ensure the `ACS` label, create or update
the pull request against the default branch, record the PR reference, and
sync the tracker when configured. Where reality turns out to contradict the
state files, do the closest faithful thing and record the deviation in the
publish report — never improvise a different flow.

**Where the cross-references below point.** Step numbers are the Inline apply
flow's in SKILL.md, which states each step in full; this file holds what binds
them together — the order, the rules each one must not break, and the report
the run leaves behind. The stacked-base remedy is
`${CLAUDE_PLUGIN_ROOT}/skills/create-pr/references/ci-convention-check.md`;
resuming is `references/resume.md`.

## What you work from

READ EVERY ONE of these before acting — workspace state, never conversation
history:

- `<partition>/ticket.json` (`<partition>` is its directory) — title, type,
  `external`;
- `<partition>/code-state.json`, `specs/*.md`, and `design.md` when the ticket
  has one;
- the resolved body template file;
- the values you settle along the way: the rendered `pr_title`, the
  `base_branch`, the ticket `branch`, and `tracker_provider`.

## GitHub call failure policy, as it applies here

Canon lives in `create-pr/SKILL.md`'s own "GitHub call failure policy
(gh is acs's only transport)" section — this reference classifies no `gh` call
itself, it only follows that classification (critical for branch/base
detection and PR create/edit; non-critical for the metadata/tracker-fill
calls). Canon hint text (`acs_lib.GH_ACCESS_HINT`, selected by
`acs_lib.gh_failure_hint(stderr)`):

> This looks like a session-level access restriction — a Claude Code
> cloud/managed session must have the Claude GitHub App connected for this
> organization by an org admin. A local Claude Code session uses your own
> `gh` authentication and should not see this.

## Ship the PR, in this order

1. **Branch, base, and the stacked-base pre-flight.** Verify the ticket branch
   exists (`git rev-parse --verify <branch>` locally, or already on origin —
   `git ls-remote origin <branch>`). Detect the base BEFORE anything is
   pushed — `gh repo view --json defaultBranchRef --jq .defaultBranchRef.name`
   — then refresh it and run the pre-flight (the helper is read-only and
   network-free, so the fetch is yours to do):

   ```bash
   git fetch origin <base>
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/stacked-base.py" check \
     --base <base> --commit-message-format "<settings.formats.commit_message>" \
     --ticket-prefix <settings.ticket_prefix>
   ```

   Exit 0 (`verdict` `clean` or `own_violations`) — nothing is stacked, carry
   on: with `notes` empty a non-conforming subject is this branch's own and
   gets the ordinary gate failure. With `notes` NON-empty the run qualified its
   own report — a commit it could not test, an index it could not build, or
   absorbed-looking content with no safe replay point — so do not conclude
   ownership from it: record the report's `message` VERBATIM as one `info`
   finding and CONTINUE, the same shape as exit 2.
   Exit 1 (`verdict` `stacked_base`) — the branch is stacked on a base that
   was squash-merged. With `settings.enforcement.checks.commit_message` on, the
   local pre-push hook refuses those subjects: do NOT push and do NOT create or
   edit a PR; surface the report's `message` VERBATIM as a blocking problem
   (it names the offending subjects and the replay command with real SHAs — a
   paraphrase drops exactly what the author needs), record it in the publish
   report, and take SKILL.md's Finish failure path. With it off (the default)
   CI refuses nothing here (ADR-0106): record the `message` VERBATIM as one
   `warning` finding and CONTINUE. The author replays the branch; you never
   rewrite it. Exit 2 (unevaluable — the base ref does not
   resolve, or the histories share no merge base; `acs stacked-base: <reason>`
   on stderr) — one `info` finding, then CONTINUE, and treat a failed
   `git fetch` the same way; an advisory pre-flight never fails a good PR.
   Only then push: `git push -u origin <branch>`; skip the push when it exists
   only on origin and is current. NEVER commit new work — uncommitted
   implementation changes are /acs:code's job: stop and ask the user (SKILL.md's
   User interaction; a non-interactive run hands off `needs_input`).
2. **Body.** Fill the resolved template into
   `steps/create-pr/pr-body.md`: replace every placeholder
   (`{ticket_id}`, `{type}`, `{title}`, `{summary}`, `{external_key}`;
   `{external_key_line}` renders as ` — tracker: <provider> <key>` when
   `ticket.external` is set, empty otherwise); replace the template's HTML comments
   with real content and DELETE the comments; fill every section strictly from the
   state files. Checklist items are `[x]` ONLY when
   code-state substantiates them (e.g. review loop passed only when
   `review.findings_open == 0`) — an unearned tick is a lie the reviewer of the
   PR will catch. Render the title with `pr-conventions.py render-title` and
   pass it verbatim.
3. **Label.** Ensure the label exists, then rely on it at create/edit time:
   `gh label create ACS --description "Created by the acs pipeline" 2>/dev/null || true`
4. **Pre-open self-check.** `pr-conventions.py check` on the filled body, with
   its bounded re-fill retry (SKILL.md step 4) — a deterministic call, not a
   subagent. A body that still fails is never opened.
5. **Create or update.** Follow the branch's state
   (`gh pr list --head <branch> --state open --json number,url,baseRefName,isDraft`):
   - No open PR for the branch:
     `gh pr create --base <default-branch> --head <branch> --title "<rendered pr_title>" --body-file steps/create-pr/pr-body.md --label ACS`
     — no `--draft`; PRs ship ready-for-review.
   - An open PR already exists: update it —
     `gh pr edit <number> --title "<rendered pr_title>" --body-file <body> --add-label ACS`,
     plus `gh pr edit <number> --base <default-branch>` when its base is wrong and
     `gh pr ready <number>` when it is a draft.
6. **Record.** `gh pr view <branch> --json number,url,baseRefName,headRefName,isDraft,labels`
   — capture `{number, url, branch, base}` into the publish report and, at
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

7. **Tracker sync** — only when `tracker_provider` is `github` or `jira` AND
   `ticket.external.key` is set (skip for `local`; when the provider is configured
   but the ticket was never synced, record an info finding instead):
   - `github`: `gh issue comment <external.key> --body "ACS: PR #<number> opened for <ticket-id> — <url>"`
   - `jira`: `acli jira workitem comment --key <external.key> --body "ACS: PR opened for <ticket-id> — <url>"`

On a resumed run (`references/resume.md`), redo exactly what the reconcile
found unfinished — re-render the title, re-fill the body, re-push, re-label,
fix the base, whatever it names — and nothing else beyond what that requires.

## The publish report

Write `steps/create-pr/iter-<n>/publish.json` (`<n>` = the run's iteration,
normally 1):

```json
{
  "artifacts": ["steps/create-pr/pr-body.md"],
  "pr": {"number": 42, "url": "https://github.com/acme/shop/pull/42", "branch": "task/SHOP-123-bulk-import", "base": "main"},
  "pushed_sha": "0f3c2ab9",
  "mode": "created",
  "commands_run": [{"cmd": "git push -u origin task/SHOP-123-bulk-import", "outcome": "pushed 0f3c2ab9"}],
  "self_check": {"passed": true, "attempts": 1},
  "tracker_sync": {"provider": "github", "key": "acme/shop#88", "result": "comment posted"},
  "metadata_fill": {"assignee": "added @me", "type_label": "task", "project": {"added": true, "status_set": true}, "reviewers": {"requested": ["@alice", "@org/team-frontend"], "skipped_reason": null, "findings": []}, "project_fields": {"priority": "High", "story_points": 3, "parent": "#42", "findings": []}, "findings": []},
  "problems": [], "clarifications_used": []
}
```

How the run ends, and what the report then says:

- **completed** — branch pushed, PR live with title/body/label, reference
  recorded in the publish report and in `states.pr`.
- **needs user input** — reality blocks you (uncommitted work on the branch,
  recorded branch missing, foreign open PR with conflicting base): ask exactly
  what you need (SKILL.md's User interaction); the report lists whatever you
  safely produced.
- **failed** — push or PR creation impossible (auth, protections, network):
  the report's `problems` and the result document's `errors` say why; report
  partial state honestly.

## Hard rules

- Spawn no subagent for any of this: the steps above are ordered commands the
  coordinator runs itself.
- Mutate ONLY what this flow covers: the push of the ticket branch, the PR
  itself (create/edit/ready/label), the `ACS` label, the tracker comment, plus
  `pr-body.md` and the publish report under `steps/create-pr/`, then the result
  document and the post-hook at Finish. Do not commit, do not merge, do not
  delete branches, do not create new branches, do not edit `ticket.json`,
  `code-state.json`, `run.json`, or any other workspace state — the post-hook
  owns what changes after the PR exists.
- Never fabricate body content: every Summary/Changes/Test-plan claim comes from
  `ticket.json`, `specs/`, `design.md`, or `code-state.json` — a section the state
  cannot fill stays honest and minimal.
- If `git push` or `gh pr create` fails, capture the exact stderr plus the
  canonical hint from `acs_lib.gh_failure_hint` in the report's `problems` and
  the result document's `errors` (critical, per create-pr/SKILL.md's
  classification — no fallback to any other transport); never retry
  destructively (no force-push, ever).

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
