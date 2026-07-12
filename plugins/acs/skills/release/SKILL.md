---
name: release
description: Assemble/verify the CHANGELOG section for a release version from the merged-ticket archive, bump the version-location files plus any extra refs configured in this repo's .acs/settings.json release block, date the section, and open an exempt release/* PR for a mandatory human merge — automating the manual release-cut steps for a repo already configured for release cuts. Fails fast if no release block is configured. Never runs git tag or gh release create itself — the privileged tag/publish step stays in the block's publish_driver. Not for opening a ticket's own PR (see /acs:create-pr) or landing/merging a PR (see /acs:merge-pr). Use when cutting a new version of a repo configured for release cuts.
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

## Step 1 — Resolve context, the `release` block, and the version argument

Call `acs_lib.build_context(cwd)` for `settings`, `workspace`, `repo_id`,
`checkout_root` — exactly as `/acs:test` does.

Resolve `release_block = ctx["settings"].get("release")`. If the release block is absent, this skill must fail fast before calling `release_notes.py` at all — missing, `null`, or an empty object all count as absent.

Do this immediately — before invoking `release_notes.py` at all — with a
clear, actionable error stating this repo's `.acs/settings.json` has no
release block configured, so `/acs:release` cannot run here; point at
`plugins/acs/schemas/settings.schema.json`'s `release` sub-schema as the
reference shape and at this marketplace's own profile #1 in
`.acs/settings.json` as a worked example. Do NOT guess a fallback shape, do
NOT silently proceed with a hardcoded marketplace path, and do NOT shell
out to `release_notes.py` in this case — there is nothing meaningful to
pass as `--release-config`. This is a coordinator-level pre-flight check,
layered on top of — not a substitute for — `release_notes.py`'s own
independent exit-2 validation of the same block shape: defense in depth,
so a malformed block is caught whether `/acs:release` is invoked directly
or `release_notes.py` is invoked by some other future caller.

**Otherwise**, serialize `release_block` to a single compact JSON string
and pass it as **`--release-config <json>`** on every `status`/`draft`/
`bump` invocation below — this single flag is the ONLY way the block
reaches `release_notes.py`; the helper itself stays `acs_lib`-free. Do NOT
emit one discrete flag per block field.

Parse `$ARGUMENTS` for the single required positional `<version>` (a bare
semver string, e.g. `0.4.2`, no leading `v`). If `$ARGUMENTS` is empty or
the value does not match a semver shape (`MAJOR.MINOR.PATCH`), fail fast
with a clear error naming the expected form — do not guess a version from
any file.

`--repo-root` for every `release_notes.py` invocation is
`ctx["checkout_root"]` — the checkout you are already running in. Unlike
`/acs:merge-pr`'s cleanup step (which must resolve the main checkout to
avoid deleting the worktree it is inside), `/acs:release` never deletes or
navigates away from any worktree — it only reads/writes files and opens a
branch+PR in place, so no special main-checkout resolution is needed.

## Step 2 — Idempotency probe (`status` FIRST, every invocation)

Mandatory first CLI call, every invocation, before any write:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/release_notes.py" status --version <version> --repo-root <checkout_root> --release-config <release_config_json>
```

Parse the JSON (`manifests_at_target`, `changelog_section_dated`,
`release_branch`, `open_pr`, `tag_exists` — resolved against the block's
`version_locations`/`changelog_path`/`tag_format`/`release_branch_format`
rather than hardcoded literals). Branch exactly:

- **`tag_exists: true`** → the version (per the block's `tag_format`) is
  already released. Report this (surface `tag_exists`'s implied tag name,
  as returned by the JSON — never recompute it from a hardcoded `v<version>`
  literal) and **STOP — no-op**. Do not bump, do not open a PR.
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
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/release_notes.py" draft --version <version> --repo-root <checkout_root> --workspace <workspace_path> --release-config <release_config_json>
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
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/release_notes.py" bump --version <version> --repo-root <checkout_root> --workspace <workspace_path> --release-config <release_config_json>
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
   git checkout -b <release_branch>
   git add <files_changed from bump's output>
   git commit -m "release: cut <release_tag>"
   git push -u origin <release_branch>
   ```

   `<release_branch>` = the block's `release_branch_format` with `{version}`
   substituted by the target version (profile #1: `release/v{version}` →
   `release/v0.4.2`). `<release_tag>` = the block's `tag_format` similarly
   substituted (profile #1: `v{version}` → `v0.4.2`). The `"release: cut "`
   prefix itself is not settings-driven — it stays the fixed convention
   matching this repo's own prior real cuts; only the version-rendering
   suffix comes from the block. A consumer's `release_branch_format` should
   be chosen to match its own `enforcement.exempt_branches` glob, or the
   release PR will fight the conventions gate — this marketplace's profile
   #1 already satisfies this (`release/v{version}` matches the existing
   `release/*` glob); this skill does not itself validate the match.

4. **Open the PR:**

   ```bash
   gh label create ACS --description "Created by the acs pipeline" 2>/dev/null || true
   gh pr create --base <base_branch> --head <release_branch> --title "release: cut <release_tag>" --body-file <coverage-report + draft_section body> --label ACS
   ```

   `<base_branch>` = the block's `base_branch` field (profile #1: `main`).
   No `--draft` — the PR is ready for review immediately. The PR title is
   the fixed `"release: cut <release_tag>"` convention (matching prior real
   cuts, tag portion block-rendered) — not rendered via `pr-conventions.py`,
   since there is no ticket to derive `settings.formats.pr_title` from and
   `release/*` is already exempt from the conventions gate. The PR body
   embeds: the coverage report (N/M/K + missing ticket ids), the
   `draft_section` text as the proposed CHANGELOG entry, and a reminder
   that `files_changed` were edited by this PR.

5. **STOP — remind the paid-eval gate.** The final action is reporting the
   PR URL and explicitly reminding the human: "Before merging, run the
   release gate — `python3 evals/run_evals.py --plugin acs --paid`." You do
   **not** run this gate yourself and do **not** wait for it — it is a
   reminder step, not a blocking check.

## SAFETY invariants

These invariants hold unconditionally, in every step, with no exception:

- The skill **NEVER** runs `git tag` or `gh release create` itself, in any
  step, under any condition. The privileged tag+publish step stays
  exclusively inside the block's `publish_driver` (profile #1:
  `.github/workflows/release.yml`, reused **unchanged** — no edit to that
  file in this ticket), triggered only by a human merging the `release/*`
  PR to the block's `base_branch`.
- The skill **NEVER** force-pushes (no forced push of any kind) and
  **NEVER** pushes directly to the block's `base_branch` — every write
  lands on the fresh `<release_branch>` (the block's `release_branch_format`
  rendered with the version), and the only push this skill ever runs is
  `git push -u origin <release_branch>`.
- The `release` settings block itself holds no secret — only file paths,
  JSON pointers, and format strings (`.acs/settings.json`'s `release` key);
  authentication for every `git`/`gh` operation is via the `gh` CLI's own
  session only. This skill DOES read a new, non-secret `release` key —
  that is compatible with never adding a new *secret* settings key, since
  no credential/token field exists in the block's schema.
- The skill **STOPS unconditionally** after opening the PR — there is no
  code path, lane, or flag that causes it to merge, tag, or publish on its
  own. This mirrors `/acs:ship` deliberately stopping at `/acs:create-pr`
  rather than auto-merging.
- The block's `publish_driver` is **reused unchanged** — this skill makes
  no edit to any publish-driver file; profile #1's own idempotent
  tag-exists guard (`.github/workflows/release.yml`) is a second,
  independent brake against a duplicate publish.

## Delegation

You perform Steps 1-3 directly, exactly as `/acs:test` does its own work
inline — you do everything yourself with Bash. You **MAY** delegate the
mechanical edit step (Step 3.2-3.3: running `bump` and the `git
checkout`/`commit`/`push` sequence) to **at most one** generic executor
subagent (a plain `Task` tool call, `subagent_type: "general-purpose"` —
not a dedicated release-executor). The delegated subagent operates on the
same resolved values the coordinator already computed — the
`--release-config` JSON string, `<release_branch>`, `<release_tag>`, and
`<base_branch>` — it never re-derives or re-resolves `settings["release"]`
itself. No dedicated agent file exists for this — a generic `Task` subagent
needs no `plugins/acs/agents/release-*.md` file on disk. There is no
planner and no verifier subagent under any circumstance: a release cut has
nothing for a planner to weigh or a verifier to independently re-derive
that the coverage report and the human PR reviewer do not already cover.

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
- **Artifacts**: release PR body at <url> (no workspace artifact — release_notes.py's write targets are exactly the files named by the resolved release block's version_locations + extra_refs + changelog_path; the durable record is the PR itself)
- **Metrics**: n/a
- **Next**: run the paid-eval gate (`python3 evals/run_evals.py --plugin acs --paid`), then request human review — or, on a no-op, nothing further to do
```
