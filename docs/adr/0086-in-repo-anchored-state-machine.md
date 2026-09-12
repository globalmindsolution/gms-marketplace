# 0086 — In-repo, main-checkout-anchored state (`.acs/state-machine`)

**Status**: Accepted · **Date**: 2026-09-01

## Context

ADR-0003 put all pipeline state in a machine-local `workspace_path` outside
the consumer repo, for one load-bearing reason: state must survive and be
shared across git worktrees so parallel-ticket sessions and per-ticket
`.lock` files work. That guarantee held only because `workspace_path` was
required and validated to sit outside the repo — a workspace resolved
relative to `cwd` inside a linked worktree would otherwise fork per worktree
and silently break sharing.

Keeping state outside the repo also means it is not easy to find or inspect
alongside the repo it belongs to, and requires mandatory setup input on every
`/acs:initialize` for a value that is mechanically derivable from the repo's
own main checkout.

## Decision

Supersede ADR-0003: anchor the acs pipeline workspace at
`<main_repo_root(cwd)>/.acs/state-machine` by default (gitignored, in-repo),
keeping `workspace_path` as an optional explicit override for anyone who
needs a different location. The default is derived via a decidable 4-step
rule rooted in `git rev-parse --git-common-dir`, hard-failing with a
`GateError` on bare-repo/submodule layouts that cannot resolve a normal
main-checkout root (the override remains the escape hatch for those
layouts). ADR-0003's worktree-sharing guarantee is preserved, not dropped:
every worktree of a repo resolves `main_repo_root()` to the same main
checkout, so every worktree keeps resolving to the same physical
`.acs/state-machine` tree. An explicit, user-confirmed one-shot migrator is
provided for repos moving off an existing external workspace.

## Consequences

State is now easy to find and grep alongside the repo it belongs to, and a
fresh `/acs:initialize` needs no required `workspace_path` input. In
exchange, moving state in-repo makes accidental commits structurally
possible for the first time; this is mitigated by a two-layer gitignore (a
tracked `.gitignore` entry plus an idempotent `info/exclude` append), but
`git add -f`/an explicit `git add <path>` still stages an ignored file
regardless of either layer.

**Accepted risk, not mitigated:** `git clean -xdf`, a hard checkout reset,
or deleting the checkout now also destroys `.acs/state-machine/` (including
`archive/`) — today, outside the repo, none of those operations touch the
workspace. Replicating state outside the repo to guard against this would
defeat the point of this decision (the workspace would no longer be "the"
state, just a cache of it), so no in-scope mitigation is provided; this is
recorded here as a documented, accepted consequence.

## Amendment — skills-independence refactor (ADR-0090)

This ADR decided **where** the workspace lives. ADR-0090 decides **what stays
in it**, and narrows this one accordingly: the workspace at
`<main_repo_root(cwd)>/.acs/state-machine` now holds the **run ledger only** —
`<skill>-state.json`, `pipeline-state.json`, `phases/<skill>/` artifacts,
verdicts, `.lock`, `lock-events.jsonl`, `clarifications.json`, and the
repo-level `tickets-index.json` / `counters.json` / `metrics.json` /
`sessions/`. The ticket's human-facing documents — `ticket.md`, `design.md`,
`analysis.md`, `api-contract.md`, `plan.md`, `test-cases.md` — move to the
**tracked** repo tree at `<settings.artifacts.tickets_path>/<ID>/` (default
`docs/tickets/<ID>/`), where they are committed on the ticket branch and
reviewed in the PR. Context, Decision and Consequences above are otherwise
unedited.

Every guarantee this ADR rests on is unaffected, because none of them was
about the documents. The 4-step `git rev-parse --git-common-dir` derivation,
the hard failure on bare-repo/submodule layouts, the optional `workspace_path`
override, and ADR-0003's worktree-sharing invariant (every worktree resolves
to the same physical state root) all apply unchanged to the ledger. The
two-layer gitignore this ADR introduced also still covers exactly what it
covered: the state root. The docs tree is deliberately **not** gitignored —
being committed is its entire purpose — so the "accidental commits are now
structurally possible" cost recorded above does not extend to it; a document
landing in a commit there is the intended outcome, not an accident.

One consequence of this ADR is strengthened rather than weakened: "state is
now easy to find and grep alongside the repo it belongs to". The half a human
actually reads is now not merely beside the repo but **in** it, under version
control. `artifacts.tickets_path: null` keeps the previous single-store
layout for any repo that does not want its ticket documents in its history.
