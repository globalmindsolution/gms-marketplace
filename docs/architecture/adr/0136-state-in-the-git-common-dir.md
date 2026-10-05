# 0136 — acs state lives in the git common directory, and state files are written through `acs.py write`

**Status**: Accepted · **Date**: 2026-10-05

**Amends**: [0086](0086-in-repo-anchored-state-machine.md) (the workspace
moves from `<main-checkout>/.acs/state-machine` to
`<git-common-dir>/acs/state-machine`; its git-plumbing derivation, its
bare/submodule refusals and its worktree-sharing invariant stand),
[0102](0102-documents-are-found-not-configured.md) (the workspace is still
fixed with no override, at the new path) and
[0105](0105-acs-runs-without-setup.md) (nothing under `.git/` is ever tracked,
so the workspace no longer depends on an ignore entry to stay out of
`git status`).

## Context

ADR-0086 anchored the workspace at `<main-checkout>/.acs/state-machine` so that
every worktree of a repo shares one state tree. Claude Code now runs sessions
in worktrees of its own — `claude --worktree`, `EnterWorktree`, and subagents
with worktree isolation — and those sessions cannot reach the main checkout:

- A session in a worktree is refused any `Edit`, `Write` or `NotebookEdit`
  whose target is in the main checkout, and any Bash call whose working
  directory is the main checkout or that points git at it (`git -C`,
  `GIT_DIR`, `cd` then git).
- With the Bash sandbox on, Bash may write only to the working directory,
  `$TMPDIR`, added directories and — from a linked worktree — the main repo's
  shared `.git` directory, except `.git/hooks/` and `.git/config`.

acs wrote every state file under the main checkout, and wrote most of them
with the `Write` tool: the coordinators write `result.json`, notes and drafts,
and 26 of the 34 agents write their `iter-<n>/` reports, notes and drafts the
same way. In a worktree session both halves were refused. Under the sandbox
even `acs.py`'s own writes to the state root failed. A pipeline started in a
worktree could not record a single step.

The one location both rules allow from any worktree is the shared git
directory, and it is also the one every worktree already resolves to:
ADR-0086 derived the state root from `git rev-parse --git-common-dir` in the
first place.

## Decision

1. **The workspace is `<git-common-dir>/acs/state-machine/`** — in an ordinary
   clone, `<main-checkout>/.git/acs/state-machine/` — with the same
   `<repo-id>/` partitioning below it. `repo.default_state_root()` derives it
   from the same git plumbing as before and joins `acs/state-machine` to the
   common directory instead of to its parent. The refusals are unchanged: a
   bare repository, a submodule and a layout whose common directory is not a
   `.git` directory still raise a `GateError`. Every linked worktree, nested
   ones under `.claude/worktrees/<name>/` included, resolves the same common
   directory and so the same state tree. There is still no setting that moves
   it.
2. **Migration is automatic and idempotent.** When the old
   `<main-checkout>/.acs/state-machine` exists and the new root does not, the
   first derivation of the root moves it: an `os.rename`, or — across
   devices, or where the rename is refused — a copy into a staging directory
   beside the new root that is then renamed into place before the old tree is
   removed. The move holds an `O_EXCL` guard in `<git-common-dir>/acs/`, so two
   hooks deriving the root at once cannot both migrate, and a staging
   directory left by an interrupted move is finished on the next call, not
   lost. Every absolute path a JSON state file stored under the old root (the
   runs index, `run.json`, session pointers, `subject/sources.json` copies,
   locks, handoff manifests) is rewritten to the same place under the new
   root, so stored paths keep resolving. A one-line
   `<main-checkout>/.acs/state-machine.MOVED` note names the new path. When
   both roots exist, acs uses the new one and leaves the old one for a human:
   `acs.py doctor` reports it under `state_root` (`legacy_leftover: true`). A
   move that cannot complete is a `GateError` (exit 2) naming both paths.
3. **No skill or agent writes a state file with the `Write` or `Edit` tool.**
   State is written through a new verb, `acs.py write <path> [--append]
   [--run R]`, which reads the content from stdin and writes it atomically
   (a temporary file in the same directory, then `os.replace`; `--append`
   adds to the end, still atomically), creating parent directories. The
   content is stdin verbatim; a terminal on stdin is refused. `<path>` is
   absolute and inside the workspace root, or relative to the run directory
   (`--run R`, by default the checkout's current run; with neither, exit 2). A
   path outside the workspace root — through `..` or through a symlink — is
   refused with exit 2 and nothing is written, and so are the
   machine-owned ledgers that have verbs of their own: `run.json`,
   `steps/<skill>/state.json`, `lock.json`, `runs-index.json`,
   `tickets-index.json`, anything under `sessions/` or `active-agents/`, and
   any `filemap.json`. On success it prints
   `{"ok": true, "path": …, "bytes": …, "appended": …, "total_bytes": …}`.
   A coordinator passes its agents the absolute run directory (`partition`
   from `acs step start`), so an agent — even one in an isolated worktree with
   no current run of its own — writes to an absolute path. Every skill and
   agent writes state in one form, with a quoted heredoc delimiter so nothing
   in the content expands:

   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write <path> <<'ACS_EOF'
   …content…
   ACS_EOF
   ```

   Repo files — code, tests and documents in the checkout — are still written
   with `Write` and `Edit` by the write roles: they are inside the session's
   worktree, which both rules allow. Survey and judge roles write only state,
   so `Write` leaves their `tools:` allowlist.
4. **The ignore entries and the settings files stay.** The `.gitignore` and
   `info/exclude` entry `.acs/state-machine/` remains, because a clone that
   has not migrated yet still needs it. `.acs/settings.json` and
   `.acs/settings.local.json` stay in the checkout: they are repo files, read
   by acs, and the team commits the first.
5. **The hooks need only the new root.** Hook scripts and the SubagentStop
   phase-artifact validation already run in Python through `default_state_root()`.
   Everything that tells the model a workspace path — the context JSON from
   `acs step start`, the task JSON a coordinator hands an agent — reports the
   resolved root, so it names the new location without a change of its own.
   `acs.py context` also reports this checkout's current `run_id` and
   `run_dir`.

## Consequences

- **A pipeline runs in a Claude Code worktree and under the Bash sandbox.** A
  worktree session writes state with one Bash call to `acs.py`, whose target
  is the shared git directory the sandbox allows; it never asks `Write` for a
  path outside its worktree. The permission rule `/acs:setup` offers for
  acs's own scripts already covers `acs.py write`.
- **Not breaking.** A repo with state at the old root is moved on the first
  acs call after the upgrade; nobody runs anything. The `.MOVED` note says
  where the state went, and `acs.py doctor` names a leftover old tree.
- ADR-0086's accepted risk shrinks: `git clean -fdx` and a hard reset no
  longer touch state, because neither reaches inside `.git/`. Deleting the
  clone still deletes it, as before. A fresh clone carries no state, as before.
- The state is less visible: it is no longer beside `.acs/settings.json` in the
  file tree. `acs.py` prints every path it writes, and the context a skill
  starts with names the root.
- A skill or agent that writes a state file with `Write` is a defect: the
  write is refused in a worktree session, and it is not atomic. AUTHORING.md
  states the rule, and the agent-contract tests hold the survey and judge
  allowlists without `Write`.
- `git worktree prune` and `git gc` leave unknown directories under `.git/`
  alone, so neither removes the workspace.
