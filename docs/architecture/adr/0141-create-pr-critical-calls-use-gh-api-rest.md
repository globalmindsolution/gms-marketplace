# 0141 — create-pr's critical GitHub calls use `gh api` REST

**Status**: Accepted · **Date**: 2026-10-09

**Amends**: [0088](0088-gh-only-github-transport-and-criticality-classification.md)
(the transport stays `gh`; the *form* of `create-pr`'s critical calls changes from
GraphQL-backed porcelain to `gh api` REST).

## Context

`/acs:create-pr` stopped at its base detect, `gh repo view --json defaultBranchRef`,
in a Claude Code session: `HTTP 403: GitHub GraphQL is not available from Claude Code
sessions; use the REST API`. Nothing was wrong with the repo, the auth or the work —
`gh repo view`, `gh pr list/view/create/edit` and `gh pr ready` are all GraphQL-backed,
and the session refuses GraphQL while serving `gh api repos/...` REST. ADR-0088 correctly
treated that failure as critical and forbade routing around it through MCP, so the run
ended with a pushed branch and no PR, and the user had to open it by hand.

## Decision

`create-pr`'s **critical** calls — the default-branch read, the open-PR detect and the PR
create/update — are `gh api` REST calls (`references/rest-transport.md`). The labels, the
Record re-read and the metadata fill keep their classification; un-drafting uses the
session's `ccr/ready_for_review` route (REST has no such call) and is non-critical.
`gh_failure_hint` gains a canonical hint for the GraphQL refusal that points at that
reference. `gh` remains the only transport and a failure is still classified, never
routed around: this changes which `gh` subcommand is used, not ADR-0088's rule.

Step 6a's `gh pr edit --add-assignee/--add-label/--add-reviewer` calls are unchanged.
They are non-critical, so where GraphQL is refused each ends as an `info` finding with a
replayable command; moving them to REST is a separate change.

## Consequences

`create-pr` completes where GraphQL is refused, and the same calls work everywhere, so
there is one code path. The commands are plainer to audit but longer than the porcelain
they replace; a test pins that the skill names no GraphQL porcelain for the critical
calls and that the reference covers each one.
