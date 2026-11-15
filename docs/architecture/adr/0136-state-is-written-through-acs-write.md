# 0136 — State files are written through `acs.py write`, never the Write tool

**Status**: Accepted · **Date**: 2026-10-06

## Context

ADR-0086 anchored the workspace at `<main-checkout>/.acs/state-machine` so that
every worktree of a repo shares one state tree, and that stands: the root is
still derived from `git rev-parse --git-common-dir`, with no override
(ADR-0102), and every linked worktree resolves the same folder at the main
checkout's root — never a folder of its own. Claude Code now runs sessions in
worktrees of its own — `claude --worktree`, `EnterWorktree`, and subagents
with worktree isolation, under `.claude/worktrees/<name>/` — and two of its
rules decide what such a session may write:

- **Worktree isolation.** A session in a worktree is refused any `Edit`,
  `Write` or `NotebookEdit` whose target is in the main checkout, and any Bash
  call whose working directory is the main checkout or that points git at it
  (`git -C`, `GIT_DIR`, `cd` then git). A Bash call that runs *from the
  worktree* and writes a file with Python is not one of those.
- **The Bash sandbox**, when it is on, lets Bash write only the working
  directory, `$TMPDIR`, added directories and the paths listed in
  `sandbox.filesystem.allowWrite`. Path rules in settings are anchored at the
  session's working directory, so a rule that is to name the main checkout's
  folder from inside a worktree has to be an absolute path.

acs wrote most of its state files with the `Write` tool: the coordinators
write `result.json`, notes and drafts, and 26 of the 34 agents wrote their
`iter-<n>/` reports, notes and drafts the same way. In a worktree session every
one of those writes is refused, because the workspace is in the main checkout.
A pipeline started in a worktree could not record a single step. Moving the
workspace was considered (into the shared git directory) and rejected: the
state is where people already look for it, beside `.acs/settings.json`, and
the refusal is about the *tool*, not the folder.

## Decision

1. **The workspace does not move.** It stays at
   `<main-checkout>/.acs/state-machine/<repo-id>/`, derived by
   `repo.default_state_root()` exactly as ADR-0086 and ADR-0102 have it, with
   the same refusals (a bare repository, a submodule) and the same one folder
   at the main checkout's root for every linked worktree, nested ones under
   `.claude/worktrees/<name>/` included.
2. **No skill or agent writes a state file with the `Write` or `Edit` tool.**
   State is written through a verb, `acs.py write <path> [--append]
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
   no current run of its own — writes to an absolute path; `acs.py context`
   reports this checkout's current `run_id` and `run_dir`. Every skill and
   agent writes state in one form, with a quoted heredoc delimiter so nothing
   in the content expands:

   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" write <path> <<'ACS_EOF'
   …content…
   ACS_EOF
   ```

   Worktree isolation does not stop it: the Bash call runs from the worktree,
   and the file is written by Python, not by a tool aimed at the main
   checkout. Repo files — code, tests and documents in the checkout — are
   still written with `Write` and `Edit` by the write roles: they are inside
   the session's own worktree.
3. **Survey and judge roles lose `Write`.** They write nothing but their own
   phase artifacts under `steps/<skill>/`, which are state, so their `tools:`
   allowlist is `Read, Glob, Grep, Bash`.
4. **`/acs:setup` offers the sandbox write rule.** Beside the permission rules
   it already offers, setup offers
   `{"sandbox": {"filesystem": {"allowWrite": ["<absolute main checkout>/.acs/state-machine"]}}}`
   so that a sandboxed Bash call in a worktree may write the workspace. The
   path is absolute — the main checkout's, also when setup runs in a linked
   worktree — because settings path rules anchor at the session's working
   directory. It is machine-specific, so it goes to the main checkout's
   `.claude/settings.local.json`, never the committed `.claude/settings.json`,
   even when the permission rules themselves were chosen for the team. The
   write is a merge: other keys and `allowWrite` entries are kept, the entry
   is added once, and a re-run adds nothing.

## Consequences

- **A pipeline runs in a Claude Code worktree session.** A worktree session
  writes state with one Bash call to `acs.py`, run from its own worktree; it
  never asks `Write` for a path outside its worktree. The permission rule
  `/acs:setup` offers for acs's own scripts already covers `acs.py write`.
- **Under the Bash sandbox it needs the setup rule.** Without the
  `allowWrite` entry a sandboxed `acs.py` call in a worktree cannot write the
  workspace; with it, it can. A user who declines the rule, or who never runs
  setup, can still run outside the sandbox or from the main checkout.
- **Nothing to migrate.** The root is where it was, so no state moves and no
  stored path changes.
- **The ignore entry stays load-bearing.** The workspace is inside the
  checkout, so the `.acs/state-machine/` entry setup writes — and the
  folder's own `.gitignore` of `*` (ADR-0105) — remain what keeps it out of
  `git status`. ADR-0086's accepted risk is unchanged: `git clean -xdf`
  still removes it.
- A skill or agent that writes a state file with `Write` is a defect: the
  write is refused in a worktree session, and it is not atomic. AUTHORING.md
  states the rule, and the agent-contract tests hold the survey and judge
  allowlists without `Write`.
