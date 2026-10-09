---
name: create-pr
description: Commit, push and open (or update) the pull request — the one acs skill that branches, commits and pushes. Whatever state the work is in — uncommitted, committed, unpushed or already pushed — it gets the changes onto a branch (splitting uncommitted ones into small reviewable commits the user confirms), pushes, and opens the PR against the default branch with the ACS label, title and body composed from workspace state. Takes a ticket id, documents, a prompt, a mix of them, or nothing (this checkout's current run); no ticket is needed — a PRD, architecture, LLD or ADR change or a prompt-driven fix ships the same way. Use whenever work in the working tree is ready for human review; the gate is a safety brake, not an order check — it refuses only a run whose recorded review left the verifier failing. Call it as your first action on such a request — do not Glob, Grep or Read for the ticket, plan, run or repo files, and do not look for a shell or run git yourself: it locates all of them itself.
argument-hint: "[ticket-id] [documents…] [prompt]"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:create-pr. Your job: get the changes we made
into a pull request, whatever state they are in — uncommitted, committed,
committed but unpushed, or already pushed. This is the ONLY acs skill that
creates a branch, stages, commits or pushes (ADR-0127). Do the work yourself,
inline, with no subagent, and use your judgment on the mechanics: the goal and
the few rules below are fixed, the commands are yours to choose.

Compose the title and body from workspace state (the run's requirements, the
ticket when there is one, `specs/`, `tech-design.md`, `steps/code/state.json`
and its review summary, the commits on the branch) — never from conversation
history, and never invent content a section has no source for.

## Start

MANDATORY first action — run exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" step start --step create-pr --args "$ARGUMENTS"
```

If it exits non-zero: STOP and surface its stderr verbatim. Do not improvise a
workaround. The pre-hook refuses only a run whose recorded review left the
verifier failing; it does not require `/acs:code` or `/acs:docs-sync` to have
run, so treat a missing `steps/code/state.json` as "no recorded implementation".

Read the printed context JSON: `run_id`, `subject`, `requirements.path`,
`ticket_id` / `ticket` (absent when there is no ticket), `partition`,
`settings.tracker`, `settings.ticket_prefix`, `design`, `checkout_root`, and
`reconcile` / `handoff_summary` (when set, read `references/resume.md` first).
`/acs:create-pr` works with a ticket id, a prompt, documents or nothing (the
checkout's current run); a ticketless run has no ticket id in commit subjects,
no ticket reference or tracker sync in the PR, and lands with
`/acs:merge-pr --pr <number>`.

## What to do

1. **Find where the work is.** Run
   `acs.py pr plan-commits --out <partition>/steps/create-pr/iter-<n>/commit-plan.json`.
   It prints the branch to use, the `base`, `groups` (the uncommitted changes
   split into reviewable commits: documents by doc set, then each slice's tests
   then code, then doc updates and e2e suites), `left_out` and `excluded`
   paths, `ahead` (commits already on HEAD past the default branch) and
   `pushed` (origin has the branch at HEAD). Use it; do not hand-build a plan.
   Nothing to commit and nothing `ahead` means nothing to ship: say so and stop
   failed.
2. **Commit what is uncommitted — with the user's say-so.** Show the plan in
   ONE question (branch, each group's subject and paths, `left_out`, `excluded`)
   with confirm / edit / cancel; apply only the edits the user names and never
   add an `excluded` path. Write the confirmed plan back to `commit-plan.json`
   (`acs.py write`), then `acs.py pr commit --plan <file>`. Commits are the
   user's history: no commit without their confirm, given at the preview or in
   the request itself ("commit it the way you split it"). Cancel commits and
   pushes nothing and finishes `interrupted`. With no groups but `ahead`
   commits, `pr commit` just cuts the branch at HEAD (detached HEAD, or the
   default branch with commits ahead).
3. **Push** the branch unless `pushed`. Never force-push; never push the
   default branch.
4. **Open or update the PR** against the default branch, ready for review
   (never a draft): a concise title (normally the ticket's title), and a body
   from the `pr-default` template (a repo's `.acs/templates/pr-default.md`
   replaces it) — Summary, Ticket, Changes (every commit on the branch past the
   default branch), Test plan, Checklist ticked only where state evidences it
   (`review.findings_open == 0` for the review tick). Label it `ACS`; a run
   with no ticket also gets `acs-exempt`, because CI fails any PR that names no
   ticket unless that label exempts it. If an open PR already exists for the
   branch, update it instead of opening a second one. Before opening, check the
   body with `pr-conventions.py check --body-file <body> --ticket-prefix <prefix>`
   and fix what it reports (a missing ticket link is expected with no ticket).
5. **Fill the metadata and sync the tracker (github tracker, ticket only).**
   `acs.py pr metadata fill --pr <number>` and a comment on the remote issue
   with the PR URL. Best-effort: a failure is a finding with its command, never
   a stop.
6. **Record** `{number, url, branch, base}` for the result.

Use whatever GitHub access works in this session — normally `gh`. The
`gh pr …` and `gh repo view` commands use GraphQL, which a Claude Code session
refuses (HTTP 403), so prefer `gh api repos/{owner}/{repo}/...` REST calls
there; if `gh` is blocked altogether, use the GitHub tools the session
provides (ADR-0141). A failed critical call (default branch, finding the open
PR, create/update) means: surface the verbatim error plus
`acs_lib.gh_failure_hint(stderr)`, try another working route once, and stop if
there is none. Everything else (labels, assignee, reviewers, Project, tracker
comment) is best-effort. Never report a PR, label or comment that was not
actually made, and say which access you used. A red "Branch / PR / commit
conventions" check after opening: read `references/ci-convention-check.md`
before believing it.

## Questions

Run `clarify.py list` first and reuse recorded answers; record every Q&A with
`clarify.py add --skill create-pr --question "..." --answer "..."` before acting
on it, and ask several open questions in one grouped interaction. The commit
preview is the only routine question. Ask something else only when reality
diverges from state (the branch carries commits the plan does not account for,
or an open PR for the branch was authored outside ACS with a conflicting base).
If you cannot reach the user and the request holds no approval of the plan,
commit nothing: record the question as `open`, finish `interrupted` /
`needs_input`, and return a `<handoff skill="create-pr" status="needs_input">`
with the plan in a `<question>`.

If your context runs low, flush progress to `steps/create-pr/handoff-context.md`,
run `handoff.py --run <run_id> --summary "<done / in-flight / next / decisions>"`,
tell the user the `continue_with` command it prints, and stop.

## Finish

MANDATORY final step, also on failure:

1. Write `steps/create-pr/result.json` through `acs.py write` (never the Write
   tool):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write steps/create-pr/result.json <<'ACS_EOF'
   {
     "status": "completed",
     "summary": "3 commits on task/SHOP-123-bulk-import; PR #42 ready for review",
     "states": {
       "pr": {"number": 42, "url": "https://github.com/acme/shop/pull/42",
              "branch": "task/SHOP-123-bulk-import", "base": "main"},
       "branch": "task/SHOP-123-bulk-import",
       "commits": [{"id": "code", "sha": "9a8b7c6d", "subject": "SHOP-123 Implement bulk import"}]
     },
     "findings": [],
     "errors": []
   }
   ACS_EOF
   ```

   `states.pr` has exactly `{number, url, branch, base}` — the /acs:merge-pr gate
   reads it; omit it entirely when no PR exists (never a stub). `branch` and
   `commits` are what `acs.py pr commit` printed, whenever it made any, even if
   a later step failed. Keep whatever is true on failure.
2. Run `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/post-create-pr.py" --result-file <that file>`.
   If it exits non-zero, surface its stderr verbatim; the pipeline gate stays
   closed until it succeeds. On success it finalizes the run and moves a
   ticket to `in_review`.
3. Under /acs:ship return ONLY a `<handoff>` XML (status, summary <=1KB naming
   the commits and PR, `<artifacts>`, `<next-step>` pointing at /acs:merge-pr).

## Completion report (normative)

Otherwise end with this block, rendered after the post-hook succeeded, `none`
where empty:

```markdown
## /acs:create-pr · <ticket-id | run-id> · <status>

- **Ticket**: <id> — <title> (<type>), or "none — <the run's prompt>"
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: commits made (short sha + subject, in order) and the paths left uncommitted; PR number and URL; base branch; head branch; `ACS` label applied
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <partition files incl. `steps/create-pr/iter-<n>/commit-plan.json`, repo paths, branch, PR URL>
- **Metrics**: <wall time>
- **Next**: review the PR, then `/acs:merge-pr <ticket-id>` (no ticket: `/acs:merge-pr --pr <number>`) — a separate, reviewed step
```
