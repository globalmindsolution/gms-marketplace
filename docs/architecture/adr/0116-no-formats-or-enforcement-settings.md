# 0116 — Branch, commit and PR style are the model's to follow, not settings

**Status**: Accepted · **Date**: 2026-10-03

**Supersedes**: the `formats` and `enforcement` settings wherever earlier ADRs
describe them — notably [0065](0065-configurable-design-spec-templates-byte-identical-defaults.md)
(the `design_template` / `design_sections` pair) and the local-hook half of
[0106](0106-ci-checks-the-ticket-link-only.md). 0106's decision that CI checks the
ticket link only stands.

## Context

`settings.formats` held the branch-name, commit-message, PR-title and template
strings, each with a placeholder vocabulary that every pre-hook validated, and
`settings.enforcement` held the toggles and exemptions of the convention check and
of the optional local git hooks. Almost none of it was read by a script. Skills
told the model to "render `settings.formats.branch_name`", which the model does
by reading a template string, and the one deterministic use — a PR-title
renderer — returned `{title}` by default.

Since ADR-0106 CI checks only that a PR description names its ticket. The local
`commit-msg` and `pre-push` hooks were the only remaining reader of the format
strings, they are bypassable, and the stacked-base pre-flight existed only to
spare an author a failing commit-subject check.

## Decision

1. **`formats` and `enforcement` are removed.** A block a repo still carries is
   accepted and ignored, and `acs.py setup detect` names it as retired.
2. **The model follows the repo's own style** for commit messages and PR titles:
   it reads `CLAUDE.md`, `CONTRIBUTING.md` and recent history like any
   contributor, and names the ticket id.
3. **What a script must parse is fixed in `acs_lib.conventions`**, not configured:
   the branch name `<type>/<ticket_id>-<slug>` (ticket detection depends on the id),
   the subject of the commit a script makes (`<ticket_id> <summary>`), the CI
   exemptions (`acs-exempt`, `release/*`, `dependabot/*`, `renovate/*`), the `ACS`
   pipeline label, an epic's `[EPIC] ` title prefix, and the built-in template
   names (a repo's `.acs/templates/<name>.md` of the same name replaces one). The
   design structure gate's sections are derived from the design template itself.
4. **The CI ticket-link check stays**, with those fixed exemptions. It reads only
   `ticket_prefix`. `templates/ci/check-conventions.py` runs without the plugin, so
   it mirrors the constants and a test keeps the copies level.
5. **The local hooks go**: the `commit-msg` and `pre-push` scripts,
   `install-hooks.sh`, the `/acs:install-hooks` skill and its eval cases. So do
   `stacked-base.py` and `pr-conventions.py render-title`. A repo that wants
   local checks uses its own pre-commit configuration.
6. **`tracker.milestone` is dropped.** A ticket's own `milestone` field stays.

## Consequences

- The settings file loses its two largest blocks; no pre-hook can refuse on a
  malformed format.
- A repo that relied on a custom branch-name format loses it: branches are
  `<type>/<ticket_id>-<slug>` everywhere.
- Style is as good as the model's reading of the repo. A repo with an unusual
  convention should say so in `CLAUDE.md`.
- The skill count is 29 (was 30); unhooked skills are 6 (was 7).
