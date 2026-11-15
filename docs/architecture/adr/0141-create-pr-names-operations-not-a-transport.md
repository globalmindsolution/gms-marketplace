# 0141 — create-pr names its GitHub operations, not one transport

**Status**: Accepted · **Date**: 2026-10-09

**Amends**: [0088](0088-gh-only-github-transport-and-criticality-classification.md)
for `/acs:create-pr` only: the "`gh` is the only transport, no fallback" rule is
relaxed there. The criticality classification of 0088 is unchanged.

## Context

`/acs:create-pr` stopped at its base detect, `gh repo view --json defaultBranchRef`,
in a Claude Code session: `HTTP 403: GitHub GraphQL is not available from Claude Code
sessions; use the REST API`. Nothing was wrong with the repo, the auth or the work.
`gh repo view`, `gh pr list/view/create/edit` and `gh pr ready` are GraphQL-backed, while
`gh api repos/...` REST was served — and the session's GitHub tools worked too. 0088
forbade routing around a failed `gh` call, so the run ended with a pushed branch and no
PR, and the PR was opened by hand. Prescribing one transport in the skill's prose made
the skill brittle exactly where the environment varies.

## Decision

`create-pr` states the **operations** it needs — read the default branch, find the open
PR for the branch, create or update the PR, label it — and the classification of each
(critical or non-critical). It no longer prescribes one transport:

- It reaches GitHub with whatever access works in the session: normally the `gh` CLI,
  preferring `gh api` REST over the GraphQL-backed `gh pr` / `gh repo view` porcelain, or
  the GitHub tools the session provides when `gh` is blocked. The skill gives the hint, not
  the command list.
- A failed critical call surfaces the verbatim error plus the canonical hint
  (`gh_failure_hint` now knows the GraphQL refusal), the skill tries another working
  access path once, and stops if there is none.
- The report says which access was used, and a PR, label or comment that was not actually
  made is never reported.

The plan also reports the state the work is in: `ahead` (commits HEAD carries past the
default branch) and `pushed` (origin has the branch at HEAD). Uncommitted, committed
and unpushed, committed on the default branch or a detached HEAD, and already pushed
all ship through the same flow: `pr commit` with no groups only cuts the branch at HEAD,
the push is skipped when `pushed`, and the PR body lists every commit past the default
branch, not just those this run made.

`create-ticket` and `merge-pr` keep 0088 as written until the same change is made there.

The skill itself shrinks to the goal, the mandatory commands and the rules that protect the
user's history (about 160 lines, down from over 600), and leaves the sequencing and the
command spelling to the model. `references/publish.md` is gone; `resume.md` and
`ci-convention-check.md` stay for the runs that need them. Its tests pin the machinery
(the commands, the CLIs, the safety rules), not the prose.

## Consequences

`create-pr` completes where one route is refused and another is open, without a human
opening the PR. The cost is that the audit trail depends on the report naming the access
used rather than on a single guaranteed transport; the credentials the other route uses
are the session's own, not a new secret in acs settings.
