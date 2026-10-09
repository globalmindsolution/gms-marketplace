# /acs:create-pr — the GitHub calls, as `gh api` REST

`gh repo view`, `gh pr list/view/create/edit` and `gh pr ready` are GraphQL-backed.
A Claude Code session refuses GraphQL (`HTTP 403: GitHub GraphQL is not available
from Claude Code sessions`), so a run that used them stopped at the base detect with
nothing wrong with the repo, the auth or the work. `gh api` REST is served everywhere,
so these are the `gh` forms to reach for first (ADR-0141); any other access that
works in the session does the same job. A failure is still reported with its hint.
`{owner}` and `{repo}` are filled by `gh` from the checkout's
remote. Read the PR title and body from files, never interpolate them into the shell.

**Base** (critical):
`gh api repos/{owner}/{repo} --jq .default_branch`

**Detect** the open PR for the branch (critical; `[]` means none):
`gh api "repos/{owner}/{repo}/pulls?head={owner}:<branch>&state=open" --jq '[.[]|{number,url:.html_url,base:.base.ref,head:.head.ref,isDraft:.draft}]'`

**Create** (critical) — the response is the PR; keep `number`, `html_url`, `base.ref`:
`gh api repos/{owner}/{repo}/pulls -f title="<PR title>" -f head=<branch> -f base=<base> -F body=@steps/create-pr/pr-body.md`
then the labels (`ACS`; no ticket: also `acs-exempt`; a ticket's type label is step 6a's):
`gh api repos/{owner}/{repo}/issues/<number>/labels -f 'labels[]=ACS' -f 'labels[]=acs-exempt'`
A milestone is `-F milestone=<number>` on the create (or the update).
Create no draft: the call sends no `draft` field.

**Update** an existing PR (critical):
`gh api -X PATCH repos/{owner}/{repo}/pulls/<number> -f title="<PR title>" -F body=@steps/create-pr/pr-body.md [-f base=<base>]`
and the `ACS` label as above.

**Ready for review** when the PR is a draft (non-critical — REST has no such call,
only GraphQL does). In a Claude Code session use the session route:
`gh api -X POST repos/{owner}/{repo}/pulls/<number>/ccr/ready_for_review`;
elsewhere `gh pr ready <number>`. A failure is one `info` finding with the command.

**Record** (non-critical re-read): `gh api repos/{owner}/{repo}/pulls/<number>`.

Step 6a's metadata calls (`gh pr edit --add-assignee/--add-label/--add-reviewer`)
are non-critical and still use the porcelain; where GraphQL is refused each ends
as an `info` finding with its replayable command, and the PR is unaffected.
