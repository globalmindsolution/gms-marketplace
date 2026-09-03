# 0002 — Hook event binding on PreToolUse(Skill)

**Status**: Accepted · **Date**: 2026-06-12 (closed the requirements' only [OPEN] question)

## Context

Claude Code has no "skill completed" hook event, but the pipeline needs
enforced pre-gating and reliable post-persistence (docs/requirements/hooks.md).

## Decision

Pre-hooks bind to `PreToolUse` matching the `Skill` tool: a dispatcher
routes by skill name to the named `pre-<skill>.py`; exit 2 blocks the skill
before any instruction runs. Post-hooks are coordinator-invoked scripts
(their inputs — status, findings, tokens — exist only in the coordinator's
context), backed by the gates: `skill-start.py` registers an `in_progress`
run first, and every downstream gate requires `runs[-1] == "completed"`. A
`SessionEnd` hook finalizes abnormal endings as `interrupted`.

## Consequences

Gating is enforced for user-typed and model-initiated invocations alike
(including /ship's direct step invocations); a skipped post-hook can close but never
open the pipeline; a hard kill leaves `in_progress` + a stale lock, which
the next run reconciles.

## Amendment — MAR-514

The Decision above says the dispatcher "routes by skill name to the named
`pre-<skill>.py`". It no longer does: `dispatch.py pre` calls
`acs_lib.GATES[skill]` **in-process**, under a bounded alarm. Context,
Decision and Consequences above are otherwise unedited.

The forwarding subprocess was itself the defect. Claude Code treats any exit
code other than 2 as "not blocked", and a subprocess that hangs, is killed, or
dies before writing an exit code takes that code with it — so the gating layer
failed *open* in exactly the cases gating exists for. Running the gate in the
dispatcher's own process means there is always a frame to convert a failure
into an explicit exit 2.

Two properties are load-bearing for that guarantee and are pinned by tests:

* The bound is raised as `dispatch.GateTimeout`, a **`BaseException`** — not
  `TimeoutError`, which subclasses `OSError` and is therefore swallowed by the
  gate path's own legitimate handlers (`acs_lib._git` returns `None` on
  `OSError`; `record_session_marker` passes on `Exception`). A swallowed alarm
  is an unbounded gate returning 0. A second, hard alarm exits the process
  outright if the first is absorbed anyway.
* `run_pre_payload` catches `SystemExit` and `KeyboardInterrupt` as well as
  `Exception`, since neither is an `Exception` and either would otherwise
  leave the frame with a non-2 exit code.

The 15 `pre-<skill>.py` files still exist but are unreachable: `hooks.json`
registers only `dispatch.py`. Deleting them, collapsing the `post-<skill>.py`
forwarders, and shrinking `.coveragerc` accordingly are tracked in MAR-521,
with the CLI that replaces them.
