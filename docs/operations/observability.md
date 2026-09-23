# Observability — reading acs's own record

acs ships no dashboard. `/acs:metrics` and `/acs:usage`, the in-session PM and
usage views that realized PRD goal **G7**, were removed together with the
usage recording that fed them — `metrics.json`, per-invocation token counts
and the transcript read behind them
([ADR 0104](../adr/0104-no-usage-dashboards-no-usage-recording.md)).

What is left to observe is the workflow itself: what ran, when, with what
outcome, what it was refused, and what it opened. That record is what
**G5 (auditability)** rests on, and this page is how to read it. Tokens, spend
and time per ticket are Claude Code's to report — its own `/cost`, the
console, or its usage exports.

## Scope and guarantees

- **Single repo.** Everything below reads the current repo's partition of the
  workspace, `<main-checkout>/.acs/state-machine/<repo-id>/` (active runs plus
  `archive/`). The location is derived, never configured
  ([ADR-0102](../adr/0102-documents-are-found-not-configured.md)).
- **Read-only.** Every command below reads state and writes nothing. Each
  prints exactly one JSON object on stdout; a usage or precondition failure
  exits 2 with actionable stderr.
- **Pretty-printed JSON throughout.** Every file named here is meant to be
  read by a person as well as by `acs.py`.

## What to read

| Question | Where it is recorded | How to read it |
|---|---|---|
| Where does a ticket stand in the pipeline? | `runs/<run-id>/run.json` (the run) and each `steps/<skill>/state.json` (its steps) | `acs.py run show [--run R]`; `acs.py run next [--run R]` for the first step not completed |
| What did one step do? | `steps/<skill>/state.json`: `states`, `findings`, `errors`, and the append-only `invocations[]` — timestamps, status, stop reason, handoff summary | `acs.py step show --step S [--run R]` |
| What is the status of every ticket? | `tickets-index.json`, which mirrors each ticket's derived status | read the file; `acs.py artifacts show --ticket T` for one ticket's documents and derived status |
| Did the file-map guard deny a write? | `invocations[-1].guard_events` on the executing step, derived into `states.review.guard_denials` | `acs.py guard events [--run R] [--skill S]` |
| Was the run gated at all? | the invocation's `gate_enforcement` verdict | printed at step start as the `DEGRADED ENFORCEMENT` notice when the gate's evidence is absent |
| Who holds a lock, and was one broken? | `lock.json`, and the audited `lock-events.jsonl` | `acs.py lock status [--run R]` |
| What did a run ship? | the PR reference on `steps/create-pr/state.json` | `gh pr view <number>` |

Working time, where a completion report prints it, is computed from an
invocation's `started_at`/`ended_at`; it is never stored or summed.

## Degraded enforcement

On a host that does not fire acs's hooks, the skills still read as
instructions and a pipeline appears to run while nothing gates it. acs reports
that state rather than leaving it silent: the `PreToolUse(Skill)` gate records
evidence that it fired, `acs.py step start` spends it once, and a run with no
accepted evidence gets a `gate_enforcement` verdict with `gated: false`, the
reason, and the enforcements it cannot confirm. `settings.hook_gates.when_absent`
decides what follows — `warn` (the default) continues ungated with the notice
on stderr, `refuse` blocks the run before anything is written.

## What is not recorded

acs records no token count, no per-role or per-model breakdown, no dollar
figure and no per-run or per-repo totals. A `metrics.json`, a `run.json`
`totals` object or an invocation's `tokens` left by an older version is
ignored.
