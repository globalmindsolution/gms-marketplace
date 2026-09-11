# 0022 — Behavioral evals are local-only; CI runs no LLM calls

**Status**: Accepted · **Date**: 2026-06-18

## Context

acs's existing eval harness (`evals/acs/harness.py`) already implements two
tiers: a free deterministic tier (runs in CI via pre-commit with
`ACS_EVAL_SOURCE=1`) and a paid behavioral tier (spawns real `claude -p`
sessions, excluded from CI). tabp's `screen-cvs` skill targets the Cowork
runtime (two-sheet Excel output, batch fan-out with Sonnet-per-CV + Opus
synthesis, project-folder file reads). Its assertable contract is the rubric
math (weighted score, must-have gate, 80/60 band cutoffs,
Recommend/Hold/Reject). Running a live model call in PR CI would (a) require a
secret unavailable on fork PRs by GitHub design, causing hard failures or silent
skips on every fork PR; (b) incur recurring per-PR cost; (c) be flaky near the
80/60 band cutoffs because tabp's reproducibility target is only 95% on a fixed
fixture set. CI currently references no eval invocations (verified: `ci.yml`
contains no eval step) (design `MAR-26/design.md:102-110`, `72-86`).

## Options considered

**A. Live API call in PR CI behind a secret:** Each PR runs a real model call on
fixtures and asserts score/band/recommendation. Hard-fails on fork PRs (GitHub
secrets unavailable by design); recurring per-PR cost; flaky near 80/60 band
cutoffs; uses `claude -p` (Claude Code runtime, not Cowork) — cannot exercise
Excel fan-out or project-folder file reads.

**B. Record/replay golden responses:** Commit recorded model responses as
fixtures; eval replays them deterministically; no live key needed. Fully
deterministic and fork-safe, but goldens drift from real model behavior without
periodic re-recording; adds recording infrastructure cost.

**C. Tiered — deterministic PR checks + gated nightly live run:** PR CI
contains only deterministic rubric/contract checks; a separate gated job
(nightly or `workflow_dispatch`) runs a real session with a trusted secret,
never triggered on fork PRs. PR ~$0 and deterministic; closest to acs's existing
free/paid split. Adds a gated CI job with its own operational complexity.

**D. Stub/mock-model rubric-only assertions:** A deterministic stub returns
canned per-requirement Met/Partial/Missing; assert the scoring engine maps them
to score/band/recommendation. Fully deterministic and fork-safe, but tests only
the deterministic scoring layer with no model judgment — weakest behavioral
signal.

**E (chosen — user C-4). Evals local-only:** All plugin evals run locally via
`run_evals.py --plugin NAME` by the developer; CI runs no evals at all; the
local full Cowork runtime can produce a real `.xlsx` scorecard without
compromise. The pre-commit free-eval smoke for acs (`ACS_EVAL_SOURCE=1`) also
runs locally.

## Decision

Adopt **E (evals local-only)**. All behavioral and LLM evals for all plugins run
locally via `python3 evals/run_evals.py --plugin NAME`. CI is restricted to
deterministic tests (`python3 -m unittest discover -s tests`) and static shape
checks (JSON validation, XSD lint, frontmatter checks). CI never invokes any
eval runner. The pre-commit free-eval smoke for acs (`ACS_EVAL_SOURCE=1 python3
evals/run_evals.py --plugin acs`) also runs locally. Option E wins on every axis
over the CI options: zero CI cost, zero flake surface, zero secret exposure on
fork PRs, and — uniquely — the local full Cowork runtime lets the tabp eval
produce a real `.xlsx` artifact rather than a schema-only proxy. CI already
references no eval invocations; the design keeps it that way and generalizes the
local harness (design `MAR-26/design.md:192-208`, `266-270`).

## Consequences

PR CI is fully deterministic and costs $0 for behavioral signal. Fork-PR
contributors see the same CI pass/fail signal as maintainers. Developers run
`python3 evals/run_evals.py --plugin acs` (or `--plugin tabp`) locally before
merging behavioral-signal changes. The `.xlsx` scorecard from a real tabp eval
run is available for inspection on the developer's machine. The trade-off is that
behavioral correctness is not enforced on every PR merge; it relies on developer
discipline to run evals before shipping behavioral-signal changes. The existing
`ACS_EVAL_SOURCE=1` pre-commit hook continues to provide a lightweight
deterministic smoke check for acs without CI LLM cost.

## Amendment — MAR-579

**Date**: 2026-09-11 · **Status**: Accepted (instrument superseded on the dogfood repo)

This repo's own per-ticket paid gate is retired. `.acs/settings.json` carried
`e2e` (and its `suites.e2e` twin) set to
`python3 evals/run_evals.py --plugin acs --paid`, so every `/acs:ship` ran the
paid tier once after `/acs:code` — roughly $7 and ~30 `claude` sessions per
ticket for a **single sample**. Both keys are removed and `post_code_test`
stays null, so the post-code test step resolves OFF by the shipped
e2e-presence rule.

The instrument is superseded, not abandoned. Quality signal moves to the
`globalmindsolution/acs-evals` repository: its **tier 1** is a deterministic
golden suite (356 cases, no LLM calls, no per-PR cost) run today from a local
acs-evals checkout with `ACS_PLUGIN_ROOT` pointed at this plugin, and its
**paid tier** — routing measurement across every shipped skill (30 probes × 5
runs against a promoted baseline) plus the PIPE-* fixture-app scenarios that
drive `/acs:code` and `/acs:docs-sync` — runs at **release cadence**. That is
already a strictly stronger release measurement than a per-ticket single
sample. The tier-1 suite becomes this repo's per-PR CI brake when the
acs-evals suite is imported into this repository — decided, not yet landed.
Until then PRs here are gated by the plugin's unit suite, the coverage
hard-fail and the free pre-commit eval tier; `.github/workflows/` carries no
eval job.

Unchanged by this amendment:

- The Decision above stands as written: behavioral and LLM evals stay
  **local-only** and CI runs no LLM calls. acs-evals' tier 1 is deterministic,
  so running it in CI, once that import lands, will not touch that rule.
- The plugin's e2e layer is untouched and stays **opt-in** for consumer repos
  (PRD G13: a repo with `settings.e2e` unset has no e2e suite and no e2e
  gate). This is a repo-local configuration choice, not a product change.
- The in-repo harness remains as an **on-demand tool**, kept in particular for
  the forge-tier scenarios (`s07_fanout_tracker_sync`, `s08_create_pr_forge`),
  which have no acs-evals counterpart.
