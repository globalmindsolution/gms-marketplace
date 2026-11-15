# 0143 — A PR with no ticket says so in its description

**Status**: Accepted · **Date**: 2026-10-09

**Amends**: [0106](0106-ci-checks-the-ticket-link-only.md) (the one CI check also
passes a description that declares it has no ticket).

## Context

The CI check fails a PR whose description names no ticket (0105, 0106). A run
with no ticket is legitimate — `/acs:create-prd`, `/acs:create-architecture` and
any prompt-driven change deliver this way (0127) — and the only way past the
check was the `acs-exempt` label. `/acs:create-pr` adds the label itself, but a
PR opened any other way (by hand, or through a session's GitHub tools) failed
with nothing the description could do about it, and the label is invisible in
the description reviewers read.

## Decision

The check passes a description that either names a ticket (an acs id, a `#<n>`
reference or an issue link) **or** has a line of its own, `Ticket: none —
<reason>` (an em or en dash, a hyphen or a colon before the reason, any case).
The reason is required: the line is a statement a reviewer can read and
disagree with, not a switch. The exemptions by label and by branch (`release/*`,
`dependabot/*`, `renovate/*`) are unchanged, as is every other rule of 0106.
The installed copy `.acs/ci/check-conventions.py` follows the template.

## Consequences

- A ticketless PR is explained where it is reviewed, with or without the label.
- The check still refuses a description that says nothing about a ticket.
- A repo that installed the check earlier keeps the old behaviour until
  `/acs:setup` refreshes its copy.
