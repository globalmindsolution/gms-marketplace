# 0149 — acs reaches GitHub through `gh api` REST only

**Status**: Accepted · **Date**: 2026-10-31

**Amends**: [0088](0088-gh-only-github-transport-and-criticality-classification.md)
— `gh` stays the only transport and its criticality classification is
unchanged; what changes is which `gh` commands acs may run.
**Generalises**: [0141](0141-create-pr-names-operations-not-a-transport.md), which fixed the
same failure for `/acs:create-pr` alone.

## Context

`/acs:release 0.7.0` stopped at its mandatory first call. `release_notes.py
status` probes for an open release PR with `gh pr list`, and a Claude Code
session answered `HTTP 403: GitHub GraphQL is not available from Claude Code
sessions`. The skill correctly treats an unanswered probe as a stop, so no cut
could ever start in such a session.

The probe was one instance of a class. gh's porcelain — `gh pr
list/view/create/edit/checks/diff/merge/update-branch`, `gh issue
view/create/edit/comment/close`, `gh label create/list`, `gh repo view`,
`gh release list` — runs on GitHub's GraphQL API. Seventeen argv literals in
the hook scripts and about seventy skill instructions used it: merge-pr's
readiness reads (both critical), create-pr's metadata fill, create-ticket's
tracker sync and remote import, the References refresh, `/acs:update`'s release
check, the PR derivation every post-hook runs. ADR-0141 had fixed create-pr's own
base detect by telling the model to prefer REST; nothing stopped the next call
site from being written the old way, and nothing covered the deterministic
code.

`gh api` against REST endpoints works wherever `gh` works, including Claude
Code sessions.

## Decision

1. **Every GitHub call acs makes is `gh api` REST**, against
   `repos/{owner}/{repo}/…` (gh fills the placeholders from the working
   directory's remote, the same repository the porcelain resolved).
2. **`acs_lib.gh_rest` is the one place the calls are built.** It holds the
   argv builders for every write, and readers that reshape REST answers into
   the documents callers already read from `gh pr view --json`: camelCase keys,
   GraphQL enum spellings (`MERGEABLE`, `BEHIND`, `APPROVED`), a
   `statusCheckRollup` built from check runs and commit statuses, and
   `isRequired` from the base branch's protection. `readiness.merge_readiness`
   and recorded fixtures keep their meaning unchanged.
   - `reviewDecision` is derived from each reviewer's latest deciding review: a
     standing request for changes outweighs any approval. ADR-0028's
     approved-review requirement still applies; a protection rule needing more
     approvals still surfaces as `BLOCKED`.
   - The required-checks signal that `gh pr checks --required` gave is now
     derived: every context the base's protection requires must have reported
     and passed. This also catches a required check that never ran.
3. **Skill text writes the REST call itself.** For example: `gh api -X PUT
   repos/{owner}/{repo}/pulls/<n>/merge -f merge_method=<strategy>`, then a
   `DELETE …/git/refs/heads/<branch>` for the branch; `…/issues/<n>/comments`
   plus `PATCH state=closed` for an issue close. A post-update-branch CI poll
   re-runs `acs.py readiness`.
4. **Projects v2 is the one exception.** `gh project …` has no REST surface gh
   can drive, so those calls stay GraphQL. They were already non-critical (or
   loud-but-non-reverting after a merge), so in a Claude Code session they
   produce a finding, never a stop.
5. **A guard keeps the class out.** `tests/acs/test_gh_rest_only.py` fails on:
   - any shipped `gh` argv whose subcommand is not `api` or `project`, or that
     is `gh api graphql`;
   - any skill, agent, docs or template paragraph that instructs a porcelain
     command, unless the paragraph is stating this rule (it names GraphQL or
     says the command is never run).

## Consequences

- `/acs:release`, `/acs:merge-pr`, `/acs:create-pr`, `/acs:create-ticket` and
  `/acs:update` work in a Claude Code session without the model improvising a
  route around a 403.
- A readiness read costs five REST calls where it was two porcelain calls: the
  pull, its reviews, the base's protection, the check runs, and the statuses.
  `step start --pr` (exempt mode) asks only for the pull.
- Projects v2 field sync still does not work in a Claude Code session; it is
  reported, as before.
- ADR-0141's "use whatever access works" stays as the last resort when `gh` is
  blocked altogether. Within `gh`, the route is now fixed.
