---
name: release
description: Assemble/verify the CHANGELOG section for a release version from the merged-ticket archive, bump both plugin manifests plus acs source.ref, date the section, and open an exempt release/* PR for a mandatory human merge — automating the manual release-cut steps. Never runs git tag or gh release create itself — the privileged tag/publish step stays in the existing Release workflow. Not for opening a ticket's own PR (see /acs:create-pr) or landing/merging a PR (see /acs:merge-pr). Use when cutting a new version of this plugin.
argument-hint: "<version>"
---

You are the coordinator of `/acs:release`, the acs one-command release-cut
utility. This is NOT a hooked pipeline skill: no skill-start, no pre/post
hooks, no `GATES` entry, no subagents beyond one optional generic executor
for the mechanical edit step (see Delegation below), no reflection loop, no
ticket, no partition, no `.lock`, no pointer file. You do everything
yourself with Bash.

Unlike `/acs:test`, which still writes a workspace artifact
(`test-runs/<run-id>/results.json`), `/acs:release` writes **no** workspace
artifact at all — the durable record is the release PR itself.
`build_context()`'s `workspace` is used only as a **read** input to
`release_notes.py draft --workspace <workspace_path>` (so it can enumerate
the merged-ticket archive) — never as a write target.

## Step 1 — Resolve context and the version argument

Call `acs_lib.build_context(cwd)` for `settings`, `workspace`, `repo_id`,
`checkout_root` — exactly as `/acs:test` does. Parse `$ARGUMENTS` for the
single required positional `<version>` (a bare semver string, e.g. `0.4.2`,
no leading `v` — this skill prefixes `v` itself where the CLI contract calls
for it, e.g. branch name `release/v<version>` and tag comparison
`v<version>`). If `$ARGUMENTS` is empty or the value does not match a semver
shape (`MAJOR.MINOR.PATCH`), fail fast with a clear error naming the
expected form — do not guess a version from `marketplace.json`'s current
value or from `roadmap.md` prose.

`--repo-root` for every `release_notes.py` invocation is
`ctx["checkout_root"]` — the checkout you are already running in. Unlike
`/acs:merge-pr`'s cleanup step (which must resolve the main checkout to
avoid deleting the worktree it is inside), `/acs:release` never deletes or
navigates away from any worktree — it only reads/writes files and opens a
branch+PR in place, so no special main-checkout resolution is needed.

## Step 2 — Idempotency probe (`status` FIRST, every invocation)

Mandatory first CLI call, every invocation, before any write:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/release_notes.py" status --version <version> --repo-root <checkout_root>
```

Parse the JSON (`manifests_at_target`, `changelog_section_dated`,
`release_branch`, `open_pr`, `tag_exists`). Branch exactly:

- **`tag_exists: true`** → `v<version>` is already released. Report the
  existing tag and **STOP — no-op**. Do not bump, do not open a PR.
- **`open_pr` non-null** (regardless of `manifests_at_target`/
  `changelog_section_dated` — an open PR means a cut is already in flight)
  → report the existing PR's number/URL (from `open_pr`) and **STOP —
  no-op**. Never open a second PR for the same version, never re-edit the
  branch.
- **Otherwise (fresh cut)** → proceed to Step 3.

This probe is the entire idempotency/re-run-safety mechanism this skill
owns — no `.lock` file, no state file, because there is no partition.

## Step 3 — Fresh cut: draft → bump → branch → PR → STOP

Only reached when Step 2 found no in-flight/done cut.

1. **Draft:**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/release_notes.py" draft --version <version> --repo-root <checkout_root> --workspace <workspace_path>
   ```

   Parse `tickets[]`, `unreleased_covered[]`, `unreleased_missing[]`,
   `coverage{merged,covered,missing}`, `draft_section`. **Surface the full
   coverage report in-session** — "N merged tickets since `<since_tag>`; M
   covered by `[Unreleased]`; K missing" plus the `unreleased_missing`
   ticket ids by name — before proceeding. This same coverage summary is
   embedded in the PR body (step 4 below) so it survives after the session
   ends.

2. **Bump:**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/release_notes.py" bump --version <version> --repo-root <checkout_root> --workspace <workspace_path>
   ```

   `--workspace <workspace_path>` here MUST be the same value passed to
   `draft` in step 1 above — `bump` regenerates the archive-authoritative
   `draft_section` internally before writing it, so this call needs the same
   archive input `draft` used. Parse `ok`, `files_changed[]`,
   `already_at_target`. If `already_at_target: true` (a defensive
   race-guard — the manifests moved between Step 2's probe and this call),
   treat this exactly like Step 2's no-op branch: report and **STOP** rather
   than proceeding to open a PR against an unexpected state.

3. **Branch, commit, push** — you (or the optional executor subagent, see
   Delegation below) run:

   ```bash
   git checkout -b release/v<version>
   git add <files_changed from bump's output>
   git commit -m "release: cut v<version>"
   git push -u origin release/v<version>
   ```

   The branch name `release/v<version>` matches
   `enforcement.exempt_branches`'s existing `"release/*"` glob — already
   present, reused unchanged, no settings edit needed.

4. **Open the PR:**

   ```bash
   gh label create ACS --description "Created by the acs pipeline" 2>/dev/null || true
   gh pr create --base main --head release/v<version> --title "release: cut v<version>" --body-file <coverage-report + draft_section body> --label ACS
   ```

   No `--draft` — the PR is ready for review immediately. The PR title is
   the fixed `"release: cut v<version>"` convention (matching prior real
   cuts) — not rendered via `pr-conventions.py`, since there is no ticket to
   derive `settings.formats.pr_title` from and `release/*` is already
   exempt from the conventions gate. The PR body embeds: the coverage
   report (N/M/K + missing ticket ids), the `draft_section` text as the
   proposed CHANGELOG entry, and a reminder that `files_changed` were
   edited by this PR.

5. **STOP — remind the paid-eval gate.** The final action is reporting the
   PR URL and explicitly reminding the human: "Before merging, run the
   release gate — `python3 evals/run_evals.py --plugin acs --paid`." You do
   **not** run this gate yourself and do **not** wait for it — it is a
   reminder step, not a blocking check.

## SAFETY invariants

These invariants hold unconditionally, in every step, with no exception:

- The skill **NEVER** runs `git tag` or `gh release create` itself, in any
  step, under any condition. The privileged tag+publish step stays
  exclusively inside `.github/workflows/release.yml`, reused unchanged — no
  edit to that file happens as part of this skill — triggered only by a
  human merging the `release/*` PR to `main`.
- The skill **NEVER** force-pushes and **NEVER** pushes directly to `main`
  — every write lands on the fresh `release/v<version>` branch, and the
  only push this skill ever runs is `git push -u origin
  release/v<version>`.
- The skill adds **NO new secret settings key** — authentication is via the
  `gh` CLI's own session only; no token, credential, or secret is read from
  `settings.schema.json` or `.acs/settings.json`.
- The skill **STOPS unconditionally** after opening the PR — there is no
  code path, lane, or flag that causes it to merge, tag, or publish on its
  own. This mirrors `/acs:ship` deliberately stopping at `/acs:create-pr`
  rather than auto-merging.
- `.github/workflows/release.yml` is reused unchanged by this skill — its
  own idempotent tag-exists guard is a second, independent brake against a
  duplicate publish.

## Delegation

You perform Steps 1-3 directly, exactly as `/acs:test` does its own work
inline — you do everything yourself with Bash. You **MAY** delegate the
mechanical edit step (Step 3.2-3.3: running `bump` and the `git
checkout`/`commit`/`push` sequence) to **at most one** generic executor
subagent (a plain `Task` tool call, `subagent_type: "general-purpose"` —
not a dedicated release-executor). No dedicated agent file exists for
this — a generic `Task` subagent needs no `plugins/acs/agents/release-*.md`
file on disk. There is no planner and no verifier subagent under any
circumstance: a release cut has nothing for a planner to weigh or a
verifier to independently re-derive that the coverage report and the human
PR reviewer do not already cover.

## Completion report (normative)

End your final message with the standard completion block, replacing the
`Ticket` line with `Run` — this skill is run-scoped, not tied to one
ticket:

```markdown
## /acs:release · <status>

- **Run**: v<version> cut attempt
- **Status**: <status> — <one line>
- **Results**: no-op (already in flight/done — <tag_exists|open_pr detail>) | PR opened: <url>
- **Findings**: coverage <N> merged / <M> covered / <K> missing (or "none — no-op path")
- **Artifacts**: release PR body at <url> (no workspace artifact — the durable record is the PR itself)
- **Metrics**: n/a
- **Next**: run the paid-eval gate (`python3 evals/run_evals.py --plugin acs --paid`), then request human review — or, on a no-op, nothing further to do
```
