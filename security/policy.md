# Security Reporting Policy

This document is the operational security reporting policy for the
**`gms-marketplace`** repository (the `acs` plugin catalog). It complements —
and does not duplicate — the root [`SECURITY.md`](../SECURITY.md), which also
covers repository hardening (branch protection, secret scanning, dependency
management).

## How to report

Report a suspected vulnerability **privately** — do not open a public issue or
pull request.

- **Preferred channel:** GitHub **private vulnerability reporting** — open the
  repository's **Security** tab and click **"Report a vulnerability."** This
  creates a private advisory visible only to maintainers.

Include the affected version or commit, a description, reproduction steps, and
the impact.

## Expected response

We aim to **acknowledge within 3 business days** of receipt. After
acknowledgement, we triage the report and share a remediation plan. Please
allow a reasonable window to fix and release before any public disclosure
(coordinated disclosure).

## Scope

In scope: the Claude Code plugin definitions (skills, agents, hooks) and
stdlib-only Python tooling (the convention checker, lifecycle hooks, helper
CLIs) that ship in this repository, plus its CI workflows. There are no
third-party runtime dependencies — nothing is fetched at runtime.

Out of scope: issues in third-party services this repository integrates with
(e.g. GitHub itself), and general hardening recommendations — see
[`SECURITY.md`](../SECURITY.md) for the repository's broader security posture.
