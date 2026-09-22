---
name: release
description: Assemble/verify the CHANGELOG section for a release version from the merged-ticket archive, plus a base_branch git-history fallback for tickets merged without an archive entry, bump the version-location files plus any extra refs configured in this repo's .acs/settings.json release block, date the section, and open an exempt release/* PR for a mandatory human merge — automating the manual release-cut steps for a repo already configured for release cuts. Fails fast if no release block is configured. Runs the repo's configured release.pre_release_gate before the cut and stops on its first failure. Never runs git tag or gh release create itself — the privileged tag/publish step stays in the block's publish_driver. Not for opening a ticket's own PR (see /acs:create-pr) or landing/merging a PR (see /acs:merge-pr). Use when cutting a new version of a repo configured for release cuts.
argument-hint: "<version>"
---

You are the coordinator of `/acs:release`, the acs one-command release-cut
utility. This is NOT a hooked pipeline skill: no step start, no pre/post
hooks, no `GATES` entry, no subagents beyond one optional generic executor
for the mechanical edit step (see Delegation below), no reflection loop, no
ticket, no partition, no `.lock`, no pointer file. You do everything
yourself with Bash.

Unlike `/acs:test`, which still writes a workspace artifact
(`test-runs/<run-id>/results.json`), `/acs:release` writes **no** workspace
artifact at all — the durable record is the release PR itself.
`build_context()`'s `workspace` is used only as a **read** input to
`release_notes.py draft --workspace <workspace_path>` (so it can enumerate
the merged-ticket archive, plus a `base_branch` git-history fallback for
tickets merged without an archive entry) — never as a write target.

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

**A non-zero exit is a STOP, never a fresh cut.** The command exits 2 with
one JSON object on stderr (`{"command", "error"}`) when it cannot resolve the
probe — most often because `gh` is absent from PATH, its auth has expired, or
a managed session is refused the repo. Surface that `error` verbatim, add the
canonical `acs_lib.gh_failure_hint()` hint when the stderr names a
session-access restriction, and stop. Do NOT treat an unresolved probe as
"no cut in flight": `open_pr` is this skill's entire re-run safety, and
proceeding on a probe that never answered is how a second release PR gets
opened for a version that already has one (ADR-0088's critical class — an
unevaluable gate is never treated as passed).

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

## Step 3 — Fresh cut: gate → draft → bump → branch → PR → STOP

Only reached when Step 2 found no in-flight/done cut.

0. **Run this repo's pre-release gate, and stop on the first failure.** A
   release is cut only from a build whose gate passed, so this runs before
   anything is edited. Read `release_block.get("pre_release_gate")` — the
   same block you resolved in Step 1:

   - **Set** (a non-empty list of command strings): run each command
     **verbatim, in the listed order, from `<checkout_root>`**, and read its
     exit code. The first non-zero exit ends the run: report status
     `failed`, name the command that failed, quote the tail of its output,
     and STOP — nothing has been drafted, bumped, branched or pushed, so
     there is nothing to undo. Fix what the gate reported and re-run
     `/acs:release <version>`. Never skip a command, reorder them,
     substitute one of your own, add a flag that relaxes one, or read a
     timeout as a pass. There is no flag that bypasses this step.

     A gate command can run for hours (this marketplace's tier-3
     measurement does). Run such a command detached, with its output and
     exit code captured to files, and wait for the exit code to appear
     before reading it — never proceed while it is still running:

     ```bash
     ( cd <checkout_root> && <command> ) > <log> 2>&1; echo $? > <log>.rc
     ```

     Keep, per command, its exit code and the last twenty lines of its
     output: step 4 embeds them in the PR body as the cut's evidence.

   - **Absent**: this repo declares no `release.pre_release_gate`, so there
     is nothing to run. Say so, say that a gate belongs in
     `.acs/settings.json` if the repo has one, and continue — the one case
     that proceeds without a gate having passed.

   Never substitute a command of your own. This skill ships to consumer
   repos whose gate you cannot know: it used to hardcode `python3
   evals/run_evals.py --plugin acs --paid`, which names a path most
   consumers do not have, and which stopped being even this marketplace's
   gate when MAR-579 retired the per-ticket paid tier. Running the wrong
   command is worse than running none.

1. **Draft:**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/release_notes.py" draft --version <version> --repo-root <checkout_root> --workspace <workspace_path> --release-config <release_config_json> --ticket-prefix <settings.ticket_prefix>
   ```

   `--ticket-prefix <settings.ticket_prefix>` is `ctx["settings"]["ticket_prefix"]`
   (this marketplace: `MAR`) — it anchors the git-history fallback's
   commit-subject match to this repo's own ticket ids, so a merge subject
   naming an unrelated `XXX-N`-shaped token elsewhere is never mistaken for
   a merged ticket here.

   Parse `tickets[]` (each entry's `source` is `"archive"` or `"git-log"`),
   `unreleased_covered[]`, `unreleased_missing[]`,
   `coverage{merged,covered,missing}`, `draft_section`. **Surface the full
   coverage report in-session** — "N merged tickets since `<since_tag>`; M
   covered by `[Unreleased]`; K missing" plus the `unreleased_missing`
   ticket ids by name — before proceeding. This same coverage summary is
   embedded in the PR body (step 4 below) so it survives after the session
   ends.

2. **Bump:**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/release_notes.py" bump --version <version> --repo-root <checkout_root> --workspace <workspace_path> --release-config <release_config_json> --ticket-prefix <settings.ticket_prefix> [--unreleased promote|replace]
   ```

   **`--unreleased` is required when `## [Unreleased]` has a body**, and the
   call is refused without it rather than guessing — writing the generated
   section over hand-written release notes destroys them silently. Choose by
   what that body is in THIS repo: `promote` when it holds the release notes
   themselves (breaking-change entries, migration steps — it moves under the
   dated heading verbatim, and every merged ticket must already be covered by
   it or the call is refused naming the ids), `replace` when it is a scratch
   list the generated ticket section says better. An empty body needs no
   flag. Step 1's `unreleased_missing[]` is what tells you `promote` will be
   accepted before you run it.

   `--workspace <workspace_path>` and `--ticket-prefix <settings.ticket_prefix>`
   here MUST be the same values passed to `draft` in step 1 above — `bump`
   regenerates the same `draft_section` internally before writing it, so
   this call needs the same archive input and fallback scope
   `draft` used (a missing/different `--ticket-prefix` here would silently
   produce a different CHANGELOG than the `draft` the human reviewed). Parse
   `ok`, `files_changed[]`,
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
   embeds: a **Pre-release gate** section — each `pre_release_gate`
   command with its exit code and output tail from step 0, or the
   statement that this repo declares none — the coverage report (N/M/K +
   missing ticket ids), the `draft_section` text as the proposed CHANGELOG
   entry, and a note that `files_changed` were edited by this PR.

5. **STOP.** The final action is reporting the PR URL and, in one line,
   that the gate passed before the cut (name the commands) or that none is
   declared. The PR is handed to a human for review and merge; you never
   merge, tag or publish (SAFETY invariants below).

## SAFETY invariants

These invariants hold unconditionally, in every step, with no exception:

- The skill **NEVER** runs `git tag` or `gh release create` itself, in any
  step, under any condition. The privileged tag+publish step stays
  exclusively inside the block's `publish_driver` (profile #1:
  `.github/workflows/release.yml`, reused **unchanged** — no edit to that
  file in this ticket), triggered only by a human merging the `release/*`
  PR to the block's `base_branch`.
- The skill **NEVER** cuts past a failing gate: when
  `release.pre_release_gate` is set, every command in it has exited 0
  before any file is edited, or the run ends `failed` with nothing written.
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
inline — you do everything yourself with Bash; the gate (Step 3.0) is
never delegated, because its exit codes are the decision. You **MAY**
delegate the mechanical edit step (Step 3.2-3.3: running `bump` and the
`git checkout`/`commit`/`push` sequence) to **at most one** generic executor
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
- **Results**: no-op (already in flight/done — <tag_exists|open_pr detail>) | gate failed at `<command>` (exit <rc>) — nothing written | PR opened: <url>
- **Findings**: gate <passed: N commands | none declared | failed at <command>>; coverage <N> merged / <M> covered / <K> missing (or "none — no-op path")
- **Artifacts**: release PR body at <url> (no workspace artifact — release_notes.py's write targets are exactly the files named by the resolved release block's version_locations + extra_refs + changelog_path; the durable record is the PR itself)
- **Metrics**: n/a
- **Next**: request human review of the release PR — or, on a gate failure, fix what it reported and re-run `/acs:release <version>` — or, on a no-op, nothing further to do
```
