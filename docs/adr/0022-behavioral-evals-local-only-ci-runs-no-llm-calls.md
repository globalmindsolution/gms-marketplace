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
