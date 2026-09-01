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
