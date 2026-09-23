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
# Eval suite (see "Two grading layers") — free structural check, then paid runs
python3 -m unittest tests.acs.test_eval_cases                  # $0: every case well-formed, every skill covered
cd plugins/acs && claude plugin eval . --tag routing --ablation none --runs 1   # PAID smoke (~$5)
cd plugins/acs && claude plugin eval . --tag routing --ablation none            # PAID, 3 runs each (~$15)
claude plugin eval acs@gms-marketplace --tag routing --ablation none           # the INSTALLED build
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
| `plugins/acs/evals/` | a **real session** routes to the right skill, or writes the right workspace state | the release gate, `release.pre_release_gate` in `.acs/settings.json` |

The eval suite is `claude plugin eval` case files in the layout
<https://code.claude.com/docs/en/plugin-evals> specifies — one directory per case,
holding `prompt.md` and `graders/*.md`, grouped under `routing/` and `artifacts/`. **The case
files are the source of truth**: there is no dataset they are rendered from and no generator.
Edit a case by editing its files. `plugins/acs/evals/README.md` is the reference for tags,
grading, and the suite's known limits — read it before quoting a number.

Because the CLI never runs in CI, `tests/acs/test_eval_cases.py` is the only thing that catches
a malformed case before a paid run does. It parses every case (through the strict reader in
`tests/acs/eval_cases.py`) and fails on an undocumented key, a bad grader type, a `max: 0`
without `min: 0`, an `input_match` that doesn't match its own skill's tool input or does match
a neighbour's, and any shipped skill without a routing case. The release gate runs it first,
so a broken case fails for free before any session is paid for.

**Source vs installed build** is a first-class distinction. A *path* target
(`claude plugin eval plugins/acs`) grades this checkout; the *named* target
`acs@gms-marketplace` grades the installed copy with the installed copy loaded — what a
consumer actually executes — so it catches packaging drift a source run cannot. Until a release
ships `plugins/acs/evals/`, the named target reports "No eval cases found": that is the
packaging answer, not a broken command.

**There used to be much more here.** A root `evals/` folder held a 355-case deterministic
golden suite, a schema-constraint generator, mutation sweeps, a tier-3 session measurer, a JSON
routing dataset with a renderer, and a Python behavioural harness. All of it was retired in
favour of the documented format; git history has it. Two limits came with that, both recorded in
the suite README: an explicit `/acs:<skill>` invocation is not reliably observable (it can be
expanded before any model turn, so no `Skill` call happens), and three routing prompts presuppose
context the empty eval workspace lacks.

**Behavioural and LLM evals never run in CI** (ADR-0022). The invariant is a grep that must keep
returning nothing: `grep -rn "run_evals\|evals/behavioural/\|plugin eval" .github/workflows/`.

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

`.acs/ci/check-conventions.py` validates branch names, commit messages and PR shape against
`.acs/settings.json` over acs's built-in defaults, which this repo keeps (branch
`{type}/{ticket_id}-{slug}`, commit `{ticket_id} {summary}` with the `MAR` prefix, a plain PR
title, required PR sections including the Ticket link, the `ACS` label). Work not backed by a
ticket needs the `acs-exempt` label. Toggles live under `enforcement.checks.*`. The checker is a
copy of `plugins/acs/templates/ci/check-conventions.py`: re-copy it, never edit it in place.

`main` is protected — branch off it, never commit to it directly.
