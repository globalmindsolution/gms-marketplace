# 0106 — CI checks the ticket link, nothing else

**Status**: Accepted · **Date**: 2026-09-23

**Builds on**: [0105](0105-acs-runs-without-setup.md), which made the PR
description, not the title, the place a PR is linked to its ticket.

## Context

The convention check `/acs:setup` installs (`acs-conventions.yml` running
`.acs/ci/check-conventions.py --mode pr`) held every pull request to five
rules:

- the branch name matched `formats.branch_name`;
- the title matched `formats.pr_title`;
- the description carried the `pr_description_sections` headings;
- the PR carried the `ACS` label;
- commit subjects matched `formats.commit_message`, when switched on.

Each existed to tie a PR to its ticket, or to prove the pipeline made it.
After ADR-0105 most of that tying had moved. The default title is `{title}`,
so the title rule accepts any text. The description's Ticket section links the
ticket, yet the section rule only checked that a heading existed, never that it
named anything. The branch rule refused every PR opened from a branch acs did
not name, even when the PR plainly belonged to a ticket.

## Decision

In CI the check enforces one rule: **the PR description names its ticket**.
That means the acs id (`<prefix>-<n>`, the repo's prefix or the default `ACS`),
a `#<n>` issue reference, or a link to an issue. The `acs-exempt` label and the
exempt branch globs (`release/*`, `dependabot/*`, `renovate/*`) still skip it,
for PRs no ticket stands behind.

- The branch-name, title, section, label and commit rules leave CI.
- `enforcement.checks.pr_title`, `checks.pr_description`, `checks.acs_label`
  and `pr_description_sections` are retired. They are accepted and ignored, so
  existing settings files stay valid.
- The optional local git hooks are unchanged. `pre-push` checks the branch name
  and commit subjects, and `commit-msg` checks one subject, against `formats.*`
  and `enforcement.checks.branch_name` / `commit_message`.
- `pr-conventions.py check`, the self-check run before a PR is opened, checks
  exactly what CI will: the ticket link, plus its two template-hygiene scans. Its
  title, label, format and section flags are accepted and ignored.
- The workflow no longer needs full git history or the title, and asks for
  `contents: read` only.
- The job keeps its name, `Branch / PR / commit conventions`. Branch protection
  requires checks by name, and renaming it would leave every repo that already
  requires it waiting on a check that never reports.

## Consequences

**A PR from any branch can merge if it names its ticket.** acs still names its
own branches `{type}/{ticket_id}-{slug}`, because that is how its skills find
the current ticket. CI no longer insists on it for PRs made some other way.

**The `ACS` label is informational.** `/acs:create-pr` still applies it, and
`/acs:merge-pr --pr` still reads it to tell a pipeline PR from an exempt one.
Nothing blocks a merge for its absence.

**Custom title and section formats are how acs renders, not rules.** A team that
sets `formats.pr_title` gets its titles rendered that way by `/acs:create-pr`,
and CI does not check them.

**The stacked-base pre-flight blocks only when the commit check is on.**
`/acs:create-pr` stopped on a branch stacked on a squash-merged base because
CI's commit check would fail on subjects the author cannot rename. CI no longer
reads them, so the stop now applies only when `checks.commit_message` is on,
where the local pre-push hook refuses them. Otherwise the replay advice is a
warning, and the PR carries the merged base's commits into review.

**The pre-push hook reads only a new branch's own commits.** For a branch the
remote does not have yet it walked the whole history. With the commit check on
and plain squash subjects on `main` (ADR-0105), that refused every first push.
It now reads the commits no remote has.

**The ticket link is a low bar, deliberately.** It proves a PR names a ticket.
It does not prove that ticket exists, or that the change matches it. Review is
still where that is judged.
