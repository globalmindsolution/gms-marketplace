---
name: handoff
description: Deliberately hand the current run off to a fresh session — flush in-flight soft context to the run directory, finalize the in-flight step as interrupted with a stop_reason, release the run's lock, and print the exact command to continue. Use when the session has grown long, the user wants to stop and resume later, or the user says "hand off" / "continue this in a new session".
argument-hint: "[run-id]"
---

You are the coordinator of `/acs:handoff` — the session-handoff utility skill.

This skill is NOT part of the gated workflow: no pre/post hooks fire for it,
you spawn NO subagents, and you do NOT run `acs step start` (it would acquire
the run's lock and open a new invocation — the opposite of what a handoff
does). You touch the consumer repo read-only; the only file you write is
`steps/<step>/handoff-context.md` inside the run directory. All state mutation
(invocation finalization, step transition, run ledger, lock release) is done by
`handoff.py` — never edit `state.json`, `run.json`, or `.lock` by hand.

A handoff is a *planned* interruption, so it beats crash recovery: it captures
the soft context that phase boundaries have not persisted yet, then releases
the run's lock so ANY session — not only this checkout — can take over.
`handed_off` is not a status. It named a REASON wearing a status: a handoff is
an interruption, `interrupted` is the one resumable state, and `stop_reason`
carries why. A handoff records `status: interrupted` with
`stop_reason: context_pressure`.

## Step 1 — Resolve the run

Resolve `<run-id>` in this order; first hit wins:

1. **Explicit argument** — `$ARGUMENTS` contains a run id (for a ticket-backed
   run that is the ticket id, e.g. `SHOP-123`).
2. **Pointer file** — `<workspace>/<repo-id>/sessions/<checkout-id>.json`,
   field `run_id` (see "Locating the workspace" below). This is the
   authoritative answer: the pointer is what `acs step start` wrote.
3. **Session context** — the run or ticket id appears in this conversation (a
   skill you were coordinating, a ticket just created or discussed).
4. **Branch name** — `git rev-parse --abbrev-ref HEAD`, match
   `<ticket_prefix>-<number>` (e.g. `SHOP-123` in `feature/SHOP-123-cart`).

If none resolves, STOP and ask the user which run to hand off (suggest
`/acs:handoff SHOP-123` with an explicit id). Never guess. You do not have to
resolve it yourself in the common case: `handoff.py` reads the same pointer and
refuses with `no current run for this checkout (nothing to hand off)` when
there is nothing to resolve.

### Locating the workspace

You need the run directory before flushing. Resolve it like the hooks do:

- **Settings** (per-key merge, most specific wins): read
  `<main-checkout>/.acs/settings.local.json`, then
  `<main-checkout>/.acs/settings.json`, then `~/.acs/settings.json`; take the
  first `ticket_prefix` found, or the default `ACS` when none sets one (no
  settings file is required). In a linked worktree also check the worktree's
  own `.acs/` files. **Workspace**: always `<main-checkout>/.acs/state-machine`,
  the same derivation `acs_lib.default_state_root()` does — no override
  exists. When it cannot be derived (a bare repo or a submodule), stop and tell
  the user that acs must be run from a regular git checkout.
- **repo-id**: from `git config --get remote.origin.url` take the last two
  path segments as `owner-name` (strip scheme, `user@`, trailing `.git`;
  replace `:` with `/`; sanitize any character outside `[A-Za-z0-9._-]` to
  `-`). Fallback: the main repo directory's basename, sanitized the same way.
- **checkout-id** (only needed for the pointer-file lookup):

```bash
python3 -c 'import hashlib,os,re,subprocess;r=subprocess.check_output(["git","rev-parse","--show-toplevel"],text=True).strip();print(re.sub(r"[^A-Za-z0-9._-]+","-",os.path.basename(r))+"-"+hashlib.sha1(os.path.abspath(r).encode()).hexdigest()[:8])'
```

The run directory is `<workspace>/<repo-id>/runs/<run-id>/`. If it holds no
`run.json`, there is no run to hand off — report that and stop.

## Step 2 — Identify the in-flight step

Read `run.json`'s `steps` map and take the one step whose `status` is
`in_progress`. Invariant I1 says there is at most one, so there is nothing to
scan and nothing to guess: the ledger either names it or nothing is in flight.
That is the same resolution `handoff.py` performs
(`acs_lib.in_flight_step` → `acs_lib.in_progress_step`), so your flush lands
where its finalization points. Do not re-derive it from the step directories
or from your memory of the conversation: the run ledger is the authority.

If no step is in flight, skip Step 3 (there is no in-flight phase to flush —
completed steps are already fully recorded in the run directory) and go
straight to Step 4.

## Step 3 — Flush soft context

Write `steps/<in-flight-step>/handoff-context.md` (create the directory if
needed). Capture ONLY what the phase artifacts and state files have NOT
already persisted — the soft context that dies with this session:

- **user clarifications & decisions** made in conversation (and their why);
- **partial findings** of the in-flight phase (what the current
  plan/execute pass has learned but not yet written out);
- **discovered gotchas** (flaky tests, surprising couplings, env quirks,
  approaches already tried and rejected);
- **next actions**, concrete and ordered.

Skeleton (keep it to a page or two; reference existing artifacts by path
instead of duplicating them):

```markdown
# Handoff context — SHOP-123 / code (iteration 2, execute in flight)

Written by /acs:handoff on 2026-06-12T09:30:00Z.

## Done (verified)
- task 1 of the plan implemented; unit tests green (steps/code/iter-1/execute.md)

## In flight
- task 2 (cart API): tests written, handler half-implemented (src/cart/api.py)

## Next actions
1. Finish the PATCH handler in src/cart/api.py; re-run pytest tests/cart/
2. Hand back to /acs:review-code for the gate (build, lint, full suite, coverage)

## User clarifications & decisions
- User chose cursor-based pagination over offset (perf on large carts)

## Partial findings (current phase)
- Existing serializer drops null quantities — workaround in tests, fix pending

## Gotchas
- tests/cart/test_api.py::test_empty is flaky under -n auto; run serially
```

`handoff.py` separately writes a derived `handoff-context.md` at the RUN root
from the ledger alone (run, workflow, in-flight step, open clarifications).
That one is a snapshot of state; yours is the soft context state cannot know.
They do not overwrite each other.

## Step 4 — Record the handoff

Run the helper (this finalizes the open invocation and the step as
`interrupted` with your summary and `stop_reason`, updates `run.json`, and
releases the run's `.lock`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/handoff.py" --run SHOP-123 \
  --summary "done: plan task 1 implemented, tests green; in flight: task 2 executor, handler partial; next: finish PATCH handler, then review-code; decisions: cursor pagination — detail in steps/code/handoff-context.md"
```

`--run` defaults to this checkout's pointer, so it can be omitted in the
common case. `--stop-reason` defaults to `context_pressure`; pass another of
`acs_lib.STOP_REASONS` when the session is stopping for a different reason.

Summary rules: one compact line, well under 1 KB, covering the four parts —
**done / in flight / next / decisions** — and pointing at
`handoff-context.md` for detail. For a longer summary write it to a temp file
and pass `--summary-file <path>` instead; the deep detail still belongs in
`handoff-context.md`, not the summary. A summary is required even when
nothing is in flight.

On success it prints JSON:

```json
{
  "ok": true,
  "run_id": "SHOP-123",
  "step": "code",
  "stop_reason": "context_pressure",
  "lock_released": true,
  "continue_with": "/acs:code SHOP-123"
}
```

If it exits non-zero, surface its stderr verbatim and stop. Known cases:

- `a handoff summary is required (--summary or --summary-file)` — write the
  summary first; it is the whole point of a planned handoff.
- `acs requires a git repository` — tell the user acs must be run inside a
  git checkout. A missing `.acs/settings.json` is never the cause: acs runs on
  its defaults, and no `/acs:setup` run is needed first.
- `ticket_prefix '<x>' is invalid …` — a hand-set prefix is malformed; the
  user fixes it in `.acs/settings.json`, or removes it to use the default
  `ACS`.
- `... acs cannot derive an in-repo state root here` (bare repo or
  submodule) — tell the user that acs must be run from a regular git
  checkout.
- `no current run for this checkout (nothing to hand off)` — ask the user
  for the run id and re-run `/acs:handoff SHOP-123`.
- `no run recorded at <path>` — the run never started, or the id is wrong;
  nothing to hand off.

## Step 5 — Report

Tell the user, compactly:

1. **How to continue** — print the `continue_with` value VERBATIM as the
   command to run in the fresh session (e.g. `/acs:code SHOP-123`). The next
   coordinator will see the step `interrupted` with its `stop_reason`, read
   the summary and `handoff-context.md`, run a light reconcile (recorded state
   trusted but cheaply verified, e.g. by re-running tests), and continue.
2. **What was flushed** — the path
   `steps/<step>/handoff-context.md` plus a one-line bullet per
   section actually captured (decisions, partial findings, gotchas, next
   actions).
3. **Lock released** — any session or worktree on this machine can now take
   the run over, not just this checkout.
4. **Scope** — the handoff targets a new session on the **same machine and
   checkout**: the state machine lives in the repo's main checkout at
   `.acs/state-machine/`, local to this machine, so cross-machine handoff is
   out of scope.

If `handoff.py` reported `"step": null`, say explicitly that **nothing was
in flight — there is nothing to hand off**: every completed step is already
recorded in the run directory, no flush file was written, and the lock (if
any) was released. Still print the `continue_with` command verbatim (it will
be `/acs:ship SHOP-123`) so the user knows exactly how to pick the run up —
`/acs:ship` resumes from the run's own cursor.

## Completion report (normative)

Every terminal outcome of a direct invocation — completed, failed, or
interrupted — ends your final message with the standard block (INTERNALS.md
"Completion report"), rendered only AFTER the helper succeeded. Same labels,
same order, `none` where empty:

```markdown
## /acs:handoff · <run-id> · <status>

- **Run**: <run-id> — <subject>
- **Status**: <status> — <summary; `stop_reason` when interrupted>
- **Results**: what was flushed to the run directory (soft context, decisions, partial findings); the in-flight invocation and step finalized `interrupted`; lock released
- **Findings**: <open findings / clarifications, or "none">
- **Artifacts**: <run-directory files, repo paths, branch, PR URL>
- **Metrics**: <wall time>
- **Next**: the exact `continue_with` command printed by `handoff.py`, e.g. `/acs:code SHOP-123` in a fresh session
```
