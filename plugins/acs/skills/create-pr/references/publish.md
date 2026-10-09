# /acs:create-pr — publishing: the details behind SKILL.md

The coordinator follows this inline; it spawns no subagent. SKILL.md owns the goal and
the order. This file holds what is easy to get wrong.

## Metadata fill and tracker sync (github tracker, ticket only)

After the PR is recorded, and on the create path and the update path alike:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" pr metadata fill --pr <number> [--author <login>]
```

It assigns the PR, applies the ticket-type label next to `ACS`, requests the
CODEOWNERS-derived reviewers with the author dropped (`--author` is optional; any spelling
of the login works), adds the PR to the Project, and sets Status and the Priority / Story
Points / Parent fields the board defines. With the tracker `local`, no ticket, or an
unsynced ticket it reports `skipped: true` and writes nothing, so the PR is byte-identical
to an unsynced repo's. It is **non-critical** throughout: exit 0 means the pass ran, not that
every field landed. Copy the printed `findings` (each an `info` finding with the command,
ready to re-run) into the publish report and never fail the PR over one.

Then, for a synced ticket on the github tracker, comment on the remote issue:
`gh issue comment <external.key> --body "ACS: PR #<number> opened for <ticket-id> — <url>"`.
Skip it for `local` and for a run with no ticket; for a configured but unsynced ticket record
an info finding instead.

## The publish report

`steps/create-pr/iter-<n>/publish.json`, through `acs.py write`:

```json
{
  "commit_plan": {"path": "steps/create-pr/iter-1/commit-plan.json", "confirmed_by": "C-1"},
  "commits": [{"id": "code", "sha": "9a8b7c6d", "subject": "SHOP-123 Implement bulk import"}],
  "pr": {"number": 42, "url": "https://github.com/acme/shop/pull/42", "branch": "task/SHOP-123-bulk-import", "base": "main"},
  "pushed_sha": "9a8b7c6d",
  "mode": "created",
  "github_access": "gh api",
  "self_check": {"passed": true, "attempts": 1},
  "tracker_sync": {"provider": "github", "key": "acme/shop#88", "result": "comment posted"},
  "metadata_fill": {"findings": []},
  "problems": []
}
```

`mode` is `created` or `updated`. On a failed run the report says honestly how far it got.

## Hard rules

- Mutate only what this flow covers: the branch and commits `acs.py pr commit` makes from the
  confirmed plan, the push of that branch, the PR itself, its labels, the tracker comment,
  and the files under `steps/create-pr/`. Do not merge, delete branches, or edit
  `ticket.json`, `steps/code/state.json` or `run.json`: the post-hook owns what changes
  after the PR exists.
- Commit ONLY through `acs.py pr commit --plan`, and only what the user confirmed: never
  `git add -A`, `git add .`, `git commit -a` or a raw `git add` / `git commit`; never commit
  to the default branch; never include a `left_out` path the user did not move into a group,
  or an `excluded` one at all. Never stash, reset, restore, clean or check out over the
  user's work.
- Never fabricate body content: every claim comes from `requirements.md`, `ticket.json`,
  `specs/`, `tech-design.md`, `steps/code/state.json` or the commits on the branch. A section
  the state cannot fill stays honest and minimal; an unverifiable point is an assumption,
  said as such.
- If the push or the PR call fails, record the exact stderr plus `acs_lib.gh_failure_hint`
  in `problems` and the result's `errors`; never retry destructively (no force-push, ever)
  and never undo a commit already made.
