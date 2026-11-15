# 0148 — /acs:setup scaffolds the document templates, and a lock keeps them current

**Status**: Accepted · **Date**: 2026-10-11

## Context

Ten templates shape what the skills write: the PR body, the four ticket
types, the tech design (`design-default`), the two audit reports and the PRD
hub and feature PRD (ADR-0147). A repo replaced one by creating
`.acs/templates/<name>.md` — but nothing put a file there, so a team had to
know the name, find the built-in inside the installed plugin and copy it before
it could change a word. And a copy, once made, wins over the built-in for
good: a plain scaffold would freeze every template at the version setup
installed, and no later improvement to the plugin's templates would reach the
repo.

## Decision

1. **`/acs:setup` offers to scaffold every document template** (recommended)
   into `.acs/templates/`, through `setup apply` with `"templates": true`
   (`acs_lib.doc_templates`). The copies are committed with the rest of setup's
   output; `templates/ci/`, the CI runners, is installed separately as before.
2. **`.acs/templates/templates.lock.json`** records, per template, the sha256 of
   the built-in it was copied from.
3. **A re-run keeps the copies current without touching the team's edits.** A
   copy still equal to what was copied is *untouched*: refreshed when the
   built-in changed. A copy that differs is *customised*: never overwritten,
   and reported as *drift* when its built-in changed since it was copied, so the
   team can compare. A copy with no lock entry (made by hand) is customised.
   With the `templates` answer absent, a repo that already has copies is still
   refreshed; `false` leaves them alone.
4. **`setup detect`** reports each template's state, and `/acs:update` points a
   repo with copies at a setup re-run when a template changed.

## Consequences

- A team edits its PR, ticket, design, audit and PRD templates in its own repo
  from day one.
- An untouched copy keeps following the plugin, at the next setup re-run.
- The lock file is committed beside the templates; editing it by hand only
  changes which copies count as untouched.
