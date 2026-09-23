# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A **Claude Code plugin marketplace** (`gms-marketplace`) whose catalog currently holds
one plugin: **acs**, an agentic software-delivery workflow. The marketplace manifest is
`.claude-plugin/marketplace.json`; the plugin source it serves is `plugins/acs`.

Python 3.9+, **stdlib only** for everything that ships. `coverage` and `jsonschema` are
needed only to reproduce CI gates locally, never by the plugin at runtime.

## Commands

```bash
# Unit + contract suites — the free layer that gates every PR
python3 -m unittest discover -s tests -v

# A single module / class / test
python3 -m unittest tests.acs.test_acs_plugin
python3 -m unittest tests.acs.test_acs_plugin.SomeTest.test_case

# The required "Tests & coverage" gate, byte-identical to .acs/settings.json tests.command
export ACS_COVERAGE=90
export ACS_COV_ROOT=$PWD COVERAGE_PROCESS_START=$PWD/.coveragerc
python3 -m coverage run -m unittest discover -s tests && python3 -m coverage combine && python3 -m coverage report --fail-under=$ACS_COVERAGE

# Pre-commit hooks (install once per clone)
pre-commit install
pre-commit run --all-files
```

**Coverage gotcha worth internalising:** `.coveragerc`'s `source`, `source_dirs` and
`data_file` are `${ACS_COV_ROOT}`-substituted **absolute** paths, because the suite drives
the hook CLIs through `subprocess.run` with `cwd=mkdtemp()`. Run coverage without exporting
`ACS_COV_ROOT` and it silently measures **nothing** — a no-op, not an error. The same applies
to any relative path introduced into that file.

```bash
# Evaluation suite (see "Two grading layers")
make -C evals help            # every target
make -C evals check           # free: fail if the case tree is stale against the dataset
make -C evals generate        # re-render the case tree from dataset/routing.json
make -C evals routing-cases   # PAID: run the suite (~$0.12/run; 40 cases x 3 runs ~ $15)

# Behavioural scenarios — free tier is deterministic and $0; paid spawns real sessions
python3 evals/behavioural/run_evals.py --plugin acs
python3 evals/behavioural/run_evals.py --plugin acs --paid   # costs money, local only
```

## Architecture

### Marketplace layout

`.claude-plugin/marketplace.json` resolves acs from the relative source `./plugins/acs`.
A relative source resolves from the marketplace checkout itself, so there is **no second ref
to keep in sync** — consumers pin by pinning the marketplace
(`claude plugin marketplace add <repo>@v0.5.0`), not per-plugin.

This matters historically: the entry previously used a `git-subdir` object with its own
`path` + `ref`, which has two readers that disagree — CI's validator resolves `path` against
the **working tree** while the installer resolves it **at `ref`**. In September 2026 each
field was individually correct and the pair was unresolvable, making the plugin uninstallable.
If you ever reintroduce an object source, `tests/acs/test_marketplace_ref_resolves.py` is the
test that guards it.

`.github/scripts/plugin_source_dirs.py` deliberately discovers plugin directories by walking
for the `.claude-plugin/plugin.json` marker rather than reading `path` from the manifest —
CI lint steps need the source *in this tree*, which is a different question from where an
install fetches it.

### Two grading layers, deliberately separate

| Layer | Asserts | Runs |
|---|---|---|
| `tests/` | a **function** does what its author intended | every PR, in CI |
| `plugins/acs/evals/` | a **real session** routes to the skill the prompt calls for | the release gate, `release.pre_release_gate` in `.acs/settings.json` |

The second layer is `claude plugin eval` in the format
<https://code.claude.com/docs/en/plugin-evals> specifies: one case directory per probe,
holding `prompt.md` and `graders/*.md`. Cases are rendered from `evals/dataset/routing.json`
by `evals/runner/gen_plugin_eval.py`, so the dataset is what gets reviewed and a hand edit in
the tree is lost on the next render. `make -C evals check` catches a stale tree, free, in CI.

`evals/behavioural/` still holds eight real-session scenarios in a bespoke Python harness,
kept for what it asserts about artifacts and hook behaviour. It is the next thing to migrate.

**There used to be a third layer** — a 355-case deterministic golden suite asserting a shipped
build's observable surface, with its own runner, schema-constraint generator, mutation sweeps
and a tier-3 session measurer. It ran no model, so it was a contract suite rather than an eval,
and routing was measured three separate times across the tiers. It was removed in favour of the
documented format; git history has it.

One capability went with it and has no replacement: **explicit `/acs:<skill>` invocation** is no
longer measurable. It is decided by the session's registration list before any model turn, so
`tool_used: Skill` reports zero calls for a probe that routed perfectly well — seven of the nine
explicit probes read as failures for that reason alone.

**Source vs installed build survives**, and is a first-class distinction rather than a detail.
`make -C evals routing-cases-installed` passes the *named* target `acs@gms-marketplace`, which
the guide resolves to the cases in the INSTALLED copy's eval directory with the installed copy
loaded — what a consumer actually executes, so it catches packaging drift a source-tree run
cannot. Until a release ships `plugins/acs/evals/`, it reports "No eval cases found": that is
the packaging answer, not a broken command.

**Behavioural and LLM evals never run in CI** (ADR-0022). The invariant is enforced by a grep
that must keep returning nothing:
`grep -rn "run_evals\|evals/behavioural/\|plugin eval" .github/workflows/`.
Keeping them out of `tests/` is also what stops `unittest discover` from collecting them.

### Inside the plugin

`plugins/acs/` ships skills (`skills/<name>/SKILL.md`), subagents (`agents/`), JSON schemas
(`schemas/`), consumer templates (`templates/`), and the hook layer (`hooks/`). All enforcement
lives in hooks, bound in `hooks/hooks.json`:

- `PreToolUse` on `Skill` — the pipeline precondition gate
- `PreToolUse` on `Write|Edit|MultiEdit|NotebookEdit` — the executor file-map guard
- `SubagentStart` / `SubagentStop` matching `^acs:` — phase-artifact validation, session bookkeeping
- `Stop`, `PreCompact`, `SessionEnd`

On a host that does not fire these events, the skills still read as instructions and a pipeline
appears to run while **nothing gates it**. That degraded state is meant to be reported, not silent.

`hooks/scripts/acs_lib/` is the shared library, one module per concern (`gates`, `lock`,
`verdict`, `settings`, `tickets`, `run`, `step`, …). Every shipped Python module is held under
**800 lines**, enforced by `tests/acs/test_module_line_budget.py` — split along seams rather than
letting a module grow.

### State and settings

Pipeline state lives **outside** the repo tree in `.acs/state-machine/<repo-id>/` (gitignored),
partitioned per ticket. Settings resolve through a cascade — user → project → `.acs/settings.local.json`
(machine-specific, gitignored) — merged over `DEFAULT_SETTINGS` in `acs_lib/settings.py`. Keys whose
value equals the default are correctly **absent** from `.acs/settings.json`; don't read absence as drift.

Two load-bearing conventions you will otherwise trip over:

- **Derived, never asserted.** Values a post-hook computes (notably a verdict's `passed`) are
  recomputed from the artifact and overwrite whatever an agent claimed, with the disagreement
  recorded. An LLM-asserted pass is not a pass.
- **`gh` is the only GitHub transport, in every environment** (ADR-0088). A failed call is never
  silently routed around to an MCP or alternative path; it surfaces as a classified finding.

### Docs

`docs/` is a full-SDLC set: `product/` (PRD, roadmap) → `requirements/` → `architecture/`
(HLD/LLD, Mermaid) → `adr/` → `principles/` · `standards/` · `quality/` · `operations/`.
`docs/README.md` is the map. ADRs are immutable records — supersede them, never edit a decision
in place. `plugins/acs/docs/` (INTERNALS, AUTHORING) is the implementation contract for anyone
changing the plugin itself.

## Conventions enforced in CI

`.acs/ci/check-conventions.py` validates branch names, commit messages and PR shape against the
`formats.*` block in `.acs/settings.json` (branch `{type}/{ticket_id}-{slug}`, commit
`{ticket_id} {summary}`, PR title `[{ticket_ref}] {title}`, required PR sections, the `ACS`
label). Work not backed by a ticket needs the `acs-exempt` label. Toggles live under
`enforcement.checks.*`.

`main` is protected — branch off it, never commit to it directly.
