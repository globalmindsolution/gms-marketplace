# acs behavioral eval subtree

This directory contains the acs-specific behavioral eval harness, runner, and
scenario registry. It is the per-plugin eval subtree introduced in MAR-33 as
part of the fully-per-plugin evals layout.

For the marketplace-level overview (why evals live here, tier policy, pre-commit
wiring, CI policy) see [`evals/README.md`](../README.md).

## Running the acs evals

### Via the top-level dispatcher (recommended)

```bash
# acs free tier (default; --plugin defaults to acs)
python3 evals/run_evals.py

# explicit plugin name
python3 evals/run_evals.py --plugin acs

# paid tier (spawns claude -p; costs money)
python3 evals/run_evals.py --plugin acs --paid

# list scenarios without running
python3 evals/run_evals.py --plugin acs --list

# run a single scenario by name (implies its tier)
python3 evals/run_evals.py --plugin acs --only install_gate_smoke

# keep sandbox temp dirs for inspection after a run
python3 evals/run_evals.py --plugin acs --paid --keep
```

### Directly (useful during scenario development)

```bash
python3 evals/acs/run_evals.py
python3 evals/acs/run_evals.py --list
python3 evals/acs/run_evals.py --paid
python3 evals/acs/run_evals.py --only install_gate_smoke
```

### Force the in-repo source tree

The pre-commit hook sets `ACS_EVAL_SOURCE=1` so it tests the source being
committed rather than a stale installed build. Use this locally too when
iterating on harness or scenario code:

```bash
ACS_EVAL_SOURCE=1 python3 evals/run_evals.py
ACS_EVAL_SOURCE=1 python3 evals/acs/run_evals.py
```

Exit code is non-zero if any selected scenario has a failing assertion.

## The acs Sandbox seam

`evals/acs/harness.py` contains the acs-specific seam between the scenario
runner and the acs plugin under test.

### `installed_scripts_dir()` and `SOURCE_SCRIPTS`

`installed_scripts_dir()` resolves the hook-scripts directory of the installed
acs build (`~/.claude/plugins/cache/<marketplace>/acs/<version>/hooks/scripts`),
picking the newest version. Falls back to the in-repo source tree
(`plugins/acs/hooks/scripts`, i.e. `SOURCE_SCRIPTS`) when no installed build is
present.

`ACS_EVAL_SOURCE=1` forces the in-repo source tree regardless of what is
installed. The `REPO_ROOT` constant is resolved as `dirname x3` from
`evals/acs/harness.py` (one more level than the former root-level location) to
reach the repo root correctly.

### `Sandbox`

`Sandbox` is a throwaway consumer repo + outside-the-repo workspace seeded with
valid `.acs/settings.json`. Use it as a context manager:

```python
from harness import Sandbox, Check  # resolves via runner sys.path

def run():
    check = Check("my_scenario")
    with Sandbox(prefix="TKT", slug="shop") as sb:
        rc, msg = sb.gate("create-ticket")          # free: drive the dispatch hook
        check.ok("gate opens", rc == 0, msg)

        result = sb.run_skill("/acs:create-ticket Add feature X")  # paid
        ticket = sb.ticket_json("TKT-1", "ticket.json")
        check.ok("ticket created", ticket["status"] == "open")
    return check
```

**`sb.gate(skill, args="")`** — runs the installed `dispatch.py pre` hook for
`/acs:<skill>`. Returns `(exit_code, stderr)`. `exit 2` means blocked; the
message says what must run first. No `claude` needed.

**`sb.run_skill(prompt, ...)`** — drives a headless `claude -p` session and
returns `{ok, result, cost_usd, num_turns, ...}`. Assert on workspace artifacts
afterwards, not on the model's text output.

**`sb.session_end()`** — runs the installed `dispatch.py session-end` hook.
Tests the abnormal-ending cleanup path.

### `Check`

`Check` collects named assertions into a pass/fail report. It is
plugin-agnostic and may be used by any plugin's scenario runner.

```python
check = Check("scenario_name")
check.ok("label", condition, "optional detail on failure")
check.eq("label", got_value, expected_value)
check.passed  # True iff all assertions passed
```

## Scenario registry

`evals/acs/scenarios/__init__.py` exposes a `SCENARIOS` list: the ordered list
of scenario modules the runner iterates. Each module exposes:

- `META` — `{"name": str, "tier": "free"|"paid"|"forge", "goal": str, "summary": str}`
- `run() -> Check` — runs the scenario and returns a `Check` with all assertions

### Adding a scenario

1. Drop `evals/acs/scenarios/sNN_<name>.py` exposing `META` and `run()`.
2. Register it in `evals/acs/scenarios/__init__.py` (`SCENARIOS` list, in run
   order).
3. Inside `run()`, import `from harness import Sandbox, Check` — the acs runner
   inserts `evals/acs/` on `sys.path` at module scope, so this resolves to
   `evals/acs/harness.py` without any path manipulation in the scenario file.
4. Assert on **artifacts** (JSON state the pipeline writes), never on the
   model's prose output.

### Current scenarios

| Name | Tier | Goal | Summary |
|------|------|------|---------|
| `install_gate_smoke` | free | G1 | Drive the installed dispatch hook through the main gate conditions |
| `create_ticket_artifacts` | paid | G1 | Run `/acs:create-ticket`; assert on ticket.json and pipeline-state.json |
| `resume_and_verify` | paid | G2–G4 | Seed code-ready state; one fresh code session must resume, pass verifier, stay under PR cap |
| `skill_triggers` | paid | routing | One NL request per skill must route to that skill (12 probes) |
| `session_end` | free | cleanup | Abnormal-ending SessionEnd hook finalizes in_progress runs correctly |

## Forge tier

The forge tier runs the real acs delivery pipeline (`/acs:create-pr`,
`/acs:merge-pr`, ...) against a dedicated, persistent, org-owned GitHub
repo, instead of the throwaway local git init `Sandbox` the free/paid tiers
use. This gets real, inspectable coverage of the parts of the pipeline that
touch an actual GitHub remote (PR creation, PR merge, branch protection)
that no local sandbox can exercise.

### `ForgeSandbox`

`ForgeSandbox` (in `evals/acs/harness.py`) is the forge-tier equivalent of
`Sandbox`: a context manager that clones the configured target repo,
operates on an ephemeral run branch, and tears itself down afterwards.

```python
from harness import ForgeSandbox

with ForgeSandbox() as sb:
    ...  # drive the real pipeline against sb.repo, on sb.run_branch
assert not sb.teardown_errors
```

On `__enter__` it: resolves and guards the configured target repo; mints a
per-run throwaway ticket prefix (`FORGE<run_id>`); clones the target into a
temp checkout; verifies the post-clone marker file; captures the default
branch and its baseline SHA; creates an ephemeral run branch
(`acs-eval/<run_id>`) off the default branch (the default branch itself is
never checked out for writes); wipes this target's workspace-partition
state; and seeds `.acs/settings.json` with the throwaway prefix.

The seeding `add`/`commit` calls are isolated from the operator's
global/system git config, HOME/XDG-derived config paths, clone-time
template state, and system gitattributes -- but a `.gitignore` or
`.git/info/exclude` actually committed in the target repo's own history is
deliberately left untouched, since that is the target repo's own concern
(see step 3 below), not the harness's isolation job.

On `__exit__` it always runs a best-effort teardown — never raises — that
closes any PR the run opened, deletes any remote branch carrying the run
id, and verifies the default branch's SHA is unchanged (drift is reported
into `sb.teardown_errors`, never force-repaired). `keep=True` (or
`ACS_EVAL_KEEP=1`) preserves the temp checkout for inspection but teardown
still runs and still reports.

### Configuration: `evals.forge_repo` / `ACS_FORGE_REPO`

The target repo is `owner/name`, read from `evals.forge_repo` in
`.acs/settings.json` / `.acs/settings.local.json` (local wins), or from the
`ACS_FORGE_REPO` env var, which overrides both. Unconfigured or malformed
values raise `ForgeConfigError` naming both sources.

### The non-production guards

Three independent guards, with **no override escape hatch**, because the
worst-case failure mode here is the forge tier accidentally running its
real, destructive delivery pipeline (branch pushes, PR merges, force-resets
on drift) against a production repo:

1. **Naming convention (G-b)** — the repo name must match
   `^acs-eval(-[a-z0-9][a-z0-9-]*)?$`.
2. **Never-self (G-c)** — the target must not be this repo's own remote.
3. **Marker file (G-d)** — the cloned checkout must contain a committed
   `.acs-eval-target` file, an explicit non-production opt-in made by the
   target repo itself (a naming-convention rename alone cannot smuggle a
   real repo in).

### Branch-per-run + teardown contract

Every forge run gets its own ephemeral branch and its own throwaway ticket
prefix, so concurrent runs against the same target never collide and the
target's default branch is only ever read, never written directly. Teardown
deletes the run's branches and closes its PRs; it reports (but never
repairs) any drift on the default branch, so an operator investigates rather
than the harness silently force-resetting a repo.

### Onboarding a forge target repo

Wiring a real target repo up is a **human-confirmed follow-up action, not
something this pipeline does autonomously** — creating a GitHub repo is a
real, hard-to-reverse action, so no `/acs:code` run or scenario creates one
on its own. Once a human has decided on the exact name/org/visibility and
created the repo, onboarding it is:

1. **Pick a name** matching `^acs-eval(-[a-z0-9][a-z0-9-]*)?$` — proposed:
   `acs-eval-target`, under the `globalmindsolution` org. **Visibility is an
   open choice a human must confirm**: private keeps throwaway pipeline
   branches/PRs out of public view but requires `gh` auth with private scope
   on every machine that runs the forge tier; public is simpler to
   authenticate but publishes every run's branches and PRs.
2. **Commit the `.acs-eval-target` marker file** at the repo root, with a
   one-line "never-production; safe to force-reset" statement — the
   authoritative opt-in the harness's marker-file guard checks for.
3. **Seed a minimal buildable baseline**: a `README.md`, one trivial source
   file, and one trivial passing test — small enough that a full clone is
   instant and a `/acs:code` run against it is cheap.
4. **Run `/acs:initialize`** in a clone of the new repo to produce its
   `.acs/settings.json` (`ticket_prefix`, `test_coverage_percent`,
   `tests.command` running that one trivial test).
5. **Wire it up**: set `evals.forge_repo` in this repo's `.acs/settings.json`
   (or export `ACS_FORGE_REPO`) to the new repo's `owner/name`.

The target repo's default branch is assumed to be `main`; confirm this at
onboarding time (`ForgeSandbox` falls back to `main` when
`origin/HEAD` is unset).
