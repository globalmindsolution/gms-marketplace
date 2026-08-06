# 0072 — Shared importable test fixture (`tests/acs/acs_case.py`)

**Status**: Accepted · **Date**: 2026-08-06

## Context

MAR-168's three residual-gap children (MAR-169, MAR-172, MAR-173) need to
add independent test files concurrently to close the per-module coverage
gaps correct measurement (ADR 0070) reveals. Before this change, the
throwaway-repo/workspace `setUp` and driving helpers lived only as a
47-line inline class defined inside `tests/acs/test_acs_plugin.py`
(223KB). Three children editing that same file concurrently multiplies
merge-conflict surface for no benefit — none of them need to change
`test_acs_plugin.py`'s own scenarios, only to reuse its fixture shape.

## Decision

Extract the fixture into a shared, importable module,
`tests/acs/acs_case.py`, and have `test_acs_plugin.py` import it rather
than define it inline. The module exposes:

- **`AcsWorkspaceCase`** — a throwaway git repo plus valid `.acs/settings.json`
  plus an isolated workspace via `.acs/settings.local.json`'s
  `workspace_path` override (`acs_case.py:31-43`), so tests never touch the
  real `~/acs-workspace`. `run_script()` (`acs_case.py:49-54`) drives the
  real hook CLIs through `subprocess.run`.
- **`load_module()`** — fresh-imports a hyphenated hook script by path
  (`importlib.util.spec_from_file_location` + `module_from_spec` +
  `exec_module`), popping any stale `sys.modules` entry first so module-level
  state doesn't leak between test cases.
- **`run_main()`** — drives a loaded module's `main()` in-process, patching
  `sys.argv`/`sys.stdin`/`sys.stdout`/`sys.stderr`, catching `SystemExit`,
  and returning `(code, out, err)`.
- **`pushd()`** — a context manager that `os.chdir`s and restores the
  original cwd in a `finally` block. It exists, rather than using
  `contextlib.chdir`, because that's Python 3.11+ and `ci.yml`'s matrix
  gates 3.9.
- **`fake_gh(bin_dir, gh_body)`** — writes an executable `gh` shim on
  `PATH`, or (when `gh_body` is `None`) simulates `gh` being entirely
  absent. The `gh_body=None` call has a caller precondition worth recording
  here since it lives only in the function's own docstring otherwise: it
  requires a **fresh, empty, writable** `bin_dir` — a second call against
  the same directory raises `FileExistsError` from `os.symlink` — and it
  returns an env whose `PATH` is `bin_dir` alone, populated with symlinks to
  `git` and `sh` only (never `gh`), so `gh` stays guaranteed-unresolvable
  even when the real `gh` shares a directory with `git` on the host.

## Consequences

**Positive.** MAR-169, MAR-172, and MAR-173 each add their own
`tests/acs/test_<module>.py` importing `acs_case`, instead of all editing
`test_acs_plugin.py` — the merge-conflict surface across the three
concurrent children drops to zero for the fixture itself. The fixture
contract (chdir restore, `sys.modules` cache-popping, the `fake_gh`
precondition above) is pinned once and inherited by every child rather than
reimplemented per test file, reducing the chance any one of them
reintroduces cwd- or module-state leakage across test methods.

**Accepted cost.** `test_acs_plugin.py`'s inline 47-line fixture class is
replaced by an import; any future change to the fixture's shape is now a
shared-surface change reviewed once, not per test file. `fake_gh`'s
`gh_body=None` precondition (fresh/empty/writable `bin_dir`) is enforced by
the function's own `os.symlink` failure mode, not asserted defensively —
callers passing a non-empty or non-writable directory get a
`FileExistsError`/`PermissionError` from the underlying call, not a
purpose-built error message.
