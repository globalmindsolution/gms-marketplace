# 0105 — acs runs without setup; the PR title carries no ticket id

**Status**: Accepted · **Date**: 2026-09-23

**Amends**: [0035](0035-pr-title-ticket-ref-token.md) (`{ticket_ref}` stays
available, but the default `pr_title` no longer uses it) and
[0086](0086-in-repo-anchored-state-machine.md) (the state root no longer
depends on `/acs:setup` adding it to the repo's `.gitignore`).

## Context

After [0102](0102-documents-are-found-not-configured.md) and the cut of
`/acs:setup` to conventions and CI, one setting was still required:
`ticket_prefix`. Every hooked skill refused with "Run /acs:setup first" until
a settings file existed, and until it named a prefix. So the first thing a new
repo met was a question, even though every other setting already had a working
default.

The default PR title, `[{ticket_id}] {title}`, repeated what the PR
description already says: its required Ticket section links the ticket.
The plugin, its schema and the CI convention checker each held their own copy
of that default, and the copies had drifted apart (`{ticket_id}` in the
plugin, `{ticket_ref}` in the schema and the checker).

## Decision

- **`ticket_prefix` defaults to `ACS`.** Tickets are `ACS-1`, `ACS-2`, and so
  on. A repo that wants its own prefix sets `ticket_prefix` by hand in
  `.acs/settings.json`. `/acs:setup` no longer asks for one.
- **No settings file is required.** `build_context` no longer refuses a repo
  without one: every key resolves to its default. A malformed value, such as
  a lowercase prefix, is still refused.
- **The state root ignores itself.** The first state write under
  `.acs/state-machine/` creates a `.gitignore` there containing `*`, so the
  workspace never shows up in `git status`, whether or not setup added the
  root `.gitignore` entry. A hook that only looks for state writes nothing, so
  a repo that never runs acs gets no folder.
- **The default `pr_title` is `{title}`.** Branch names and commit messages
  still carry the ticket id, because that is how every skill finds the
  current ticket. `{ticket_id}` and `{ticket_ref}` stay available for a repo
  that wants the id in its titles.
- **The CI checker uses the same defaults.** `check-conventions.py` runs
  without the plugin, so it keeps its own copy. A test now fails when that
  copy, the schema's documented defaults or the plugin's defaults differ.
  With no settings file, the checker checks against the defaults instead of
  failing closed.

## Consequences

**Setup is optional.** It is how a team changes a convention format or
installs the CI gates, not a step every repo must take first.

**The prefix is not repo-specific by default.** Two repos that both keep the
default mint `ACS-1`. Ids are per-repo state and never cross repos, so the
overlap is cosmetic. A repo that shares a tracker with others sets its own
prefix.

**Changing the prefix later strands older ids.** A repo that mints `ACS-n`
tickets and then sets `SHOP` stops matching the `ACS-n` branches. This was
already true of any prefix change.

**A hand-merged ticket may drop out of the release notes' git-log
fallback.** A squash merge takes its commit subject from the PR title, so under
the default title that subject carries no ticket id. `/acs:release` reads the
merged-ticket archive first, and `/acs:merge-pr` writes it, so a ticket merged
through acs is unaffected. The fallback exists for tickets merged by hand, and
it reads only commit subjects, so such a ticket is now found only if its
subject still names it. A repo that merges by hand and relies on the fallback
keeps the id in its titles: `"pr_title": "[{ticket_ref}] {title}"`. The ticket
counter's reconciliation scan is unaffected, because it also reads commit
bodies, branch names and the committed `docs/tickets/<ID>/` folders.

**Existing repos are unaffected.** A repo whose settings name a prefix or a
`pr_title` keeps them.
