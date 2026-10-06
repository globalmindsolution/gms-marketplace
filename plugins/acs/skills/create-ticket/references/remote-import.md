# /acs:create-ticket — importing a remote tracker issue

Open this when `$ARGUMENTS` may be a remote key, before planning. Where
"below" points: the "GitHub call failure policy" and Steps 1-5 are SKILL.md's.

Decide BEFORE planning whether `$ARGUMENTS` is a remote key for
`settings.tracker.provider`:

- provider `github` and `$ARGUMENTS` is `#123`, a bare integer, or a GitHub issue
  URL: pull with `gh issue view 123 --json number,title,body,labels,assignees,url`.
- provider `local`, or no match: not an import — the requirements
  (`requirements.path`) are the request.

On import: if the pull fails — **critical**, a gate input this run cannot
proceed without — stop and surface the CLI error verbatim plus the canonical
hint from `acs_lib.gh_failure_hint(stderr)` (see "GitHub call failure
policy" below), with no fallback to any other transport. Otherwise seed the
working title/description from the remote issue and record the mapping
`external = {"provider": "github", "key": "123"}` for Step 3 to write into `ticket.json`. Then run the NORMAL
analysis below on the imported description — imports get the same clarification,
typing, PRD trace, authoring and review as a local request (an issue labelled as a
bug is a strong `bug` signal). Never create a new remote issue for an imported
ticket: the mapping points at the existing one.
