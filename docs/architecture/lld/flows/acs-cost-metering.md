# LLD Flow — acs token/time metering (measure/persist and read/render)

How `acs` measures and persists real elapsed time and real token counts for
every hooked skill run, and how `/acs:usage`/`/acs:metrics` render those
figures back out. Two coupled paths: **measure/persist** (every hooked skill
run, at its pre-hook and post-hook) and **read/render** (`/acs:usage`,
`/acs:metrics`), read-only on the render side. ADR 0082 records the decision
this flow implements.

[ADR 0103](../../../adr/0103-no-status-line-no-cost-metering.md) removed this
flow's dollar-cost half: the status line that sampled Claude Code's cost
payload, `cost_sampler.py`, the per-checkout sample log and allocation cursor,
and every cost and API-duration figure on a run entry, a total or a
dashboard. acs records no dollar figure. The file keeps its original name.

## Sequence diagram — measure/persist path

```mermaid
sequenceDiagram
    participant Coord as Coordinator (skill session)
    participant CC as Claude Code runtime
    participant Pre as dispatch.py pre / acs_lib.run_pre_payload
    participant Start as acs step start
    participant Post as post-<skill>.py / acs_lib.finalize_invocation
    participant UR as usage_reader.py
    participant TR as Transcript store (session .jsonl + subagents/)
    participant WS as Workspace (marker, invocation, run.json, metrics.json)

    Coord->>CC: /acs:<skill> invoked
    CC->>Pre: PreToolUse(Skill) envelope (session_id, transcript_path, cwd, tool_input.skill)
    Pre->>Pre: build_context
    Pre->>WS: record_session_marker -- sessions/<checkout_id>/session.json, only when record_marker and the root guard allow, in its own try/except
    Pre->>Pre: GATES[skill] check (gate_outcome)
    Pre->>WS: gate passed -- _mark_step_started opens the invocation (started_at, status in_progress)
    Pre-->>CC: exit 0 (pass) or exit 2 (blocked) -- the marker write never affects this exit code
    Coord->>Start: acs step start --step <skill>, the coordinator's first action
    Start->>WS: append_invocation enriches the already-open invocation (gate verdict) rather than appending a second one
    Coord->>Post: skill finishes, coordinator calls the post-hook with the result document
    Post->>Post: validate_result -- a cost_usd key is an undeclared property since ADR 0103
    Post->>WS: finalize_invocation reads invocations[-1] (session_id, transcript_path, started_at), stamps ended_at and status
    alt invocation has no session_id or transcript_path
        Post->>WS: tokens all-zero, role_usage=[], model_usage=[] -- no transcript I/O (new-ticket.py's synthetic create-ticket runs land here)
    else session_id and transcript_path present
        Post->>UR: read_transcript_usage(transcript_path, started_at, ended_at, skill)
        UR->>TR: stream the exact transcript_path, then a recursive walk of dirname(transcript_path)/<session_id>/subagents/*.jsonl (never a constructed slug, never *.meta.json)
        TR-->>UR: message.usage (4 integer fields) + model + timestamp + attributionSkill/attributionAgent, in-window records only
        alt transcript unreadable, cap breached (32 MiB / 64 files), empty window, or zero real tokens resolved
            UR-->>Post: {degraded: true, reason}
            Post->>WS: tokens all-zero, role_usage=[], model_usage=[]
        else at least one in-window usage record
            UR-->>Post: {degraded: false, role_usage: [{role, input, output, cache_creation, cache_read}, ...], model_usage: [{model, input, output, cache_creation, cache_read}, ...], excluded_token_share}
            Post->>WS: persist role_usage, model_usage, and tokens summed from role_usage
        end
    end
    Post->>WS: update_metrics -- invocations, working_seconds (a None-elapsed run is excluded from the sum), runs_timed/runs_untimed, tokens by class
```

## Sequence diagram — read/render path

```mermaid
sequenceDiagram
    actor PM as PdM or tech lead
    participant CC as Claude Code runtime
    participant Usage as /acs:usage or /acs:metrics coordinator
    participant Agg as metrics_aggregate.py
    participant WS as Workspace (run.json, step state, metrics.json)
    participant Render as metrics_render.py

    PM->>CC: /acs:usage (or /acs:metrics)
    CC->>Usage: expand skill, run coordinator
    Usage->>Agg: python3 metrics_aggregate.py
    Agg->>WS: read run.json + steps/<skill>/state.json invocations, per ticket, and metrics.json
    WS-->>Agg: invocations -- started_at/ended_at, tokens, role_usage, model_usage
    Agg->>Agg: elapsed_seconds via acs_lib -- None renders "no data", never 0
    Agg->>Agg: working-time averages divide metrics.json's working_seconds by the ticket count and by the merged-PR count -- no data when either is zero
    Agg->>Agg: _accumulate_burn buckets every role_usage entry into panel 6 by role, including a first-class coordinator bucket, every model_usage entry into usage_by_model by model, at both repo and per-ticket scope, and each entry's wall-clock seconds into a per-skill accumulator for usage_by_ticket.skills[] (zero extra file reads)
    Agg->>Agg: _apply_panel6_shares computes repo-scope token_share_pct once, post-loop, and _usage_by_ticket_panel finalizes ticket-scope token shares
    Agg-->>Usage: aggregate JSON -- panels 1-7 plus usage_by_model plus usage_by_ticket plus meta.degraded entries, with no cost or API-duration key even when an older run entry carries one
    Usage->>Render: pipe JSON, render the requested view
    Render-->>Usage: terminal text or self-contained HTML
    Usage-->>PM: the dashboard, tokens and wall-clock time only, with a degraded summary
```

No write, lock, or gate involvement on the read/render path — it is a pure
function of workspace JSON already written by the measure/persist path above.

## Step annotations

### Measure/persist — correlation capture (pre-hook)

`record_session_marker` persists the fields present on the
`PreToolUse(Skill)` envelope — `session_id`, `transcript_path`, `cwd`,
`checkout_id` (from `build_context`), `hook_event_name`, and the skill name
read from `tool_input.skill` — never a constructed or guessed value.

**Two conditions gate it, and both were added after this diagram was first drawn.**
`run_pre_payload` takes `record_marker`, which `acs gate` passes as `False`:
`gate` answers "would this pass?" and is not a `PreToolUse` event, so routing
it through the hook path used to rewrite the marker with a null `session_id`
and cost the NEXT run its attribution. And the root guard declines to
overwrite a marker that already carries a `session_id` with a payload that
does not. So a missing field is written as `null` only when the write happens
at all; where either condition declines, nothing is written. The marker call sits **between**
`build_context` and the skill's own `GATES[skill]` check inside `run_pre_payload`,
wrapped in its own `try/except Exception: pass`, so a bug in the marker path
can never turn the outer fail-closed handler (exit 2) into a blocked
pipeline over an unrelated audit-trail write.

### Measure/persist — threading onto the invocation

`acs_lib.accepted_session_marker` is the accept rule: it takes the marker
only when `marker.checkout_id` matches the current checkout **and** the
marker is no older than 15 minutes (bounded by the pre-hook's own 30s/25s
timeouts). `append_invocation` takes an accepted marker as `session` and
copies `session_id`/`transcript_path`/`checkout_id` onto the open invocation.
A rejected or stale marker means `session_id = null` on the invocation, which
`usage_reader` treats as `degraded, reason="no_session_marker"` at finalize
time. It never falls back to constructing a path.

**Known gap.** Neither opener passes `session` today — not the pre-hook's
`_mark_step_started`, and not `acs step start` — so a live invocation reaches
`finalize_invocation` without a `session_id` and takes the no-transcript
branch of the diagram above. The accept rule and the copy are implemented
and tested on their own; the call that joins them is missing.

### Measure/persist — token measurement (post-hook)

`finalize_invocation` calls `_measure_run_usage`, which short-circuits before
any transcript I/O when the invocation carries no `session_id`/
`transcript_path` — deliberately: `new-ticket.py` synthesizes and immediately
finalizes a `create-ticket` run per epic child with no session, and an
unguarded scan would run once per child. When a session is present,
`usage_reader.read_transcript_usage` reads the exact recorded file plus a
recursive walk of its `subagents/` subtree — never a `*.meta.json` sidecar,
since only `*.jsonl` paths are ever enumerated — and returns per-role and
per-model token buckets (`role_usage`, `model_usage`, MAR-3) or a degraded
reason. Unattributed same-window tokens land in an `unattributed` role
bucket rather than inflating an attributed role (C-8); the reader also
reports `excluded_token_share`, which the invocation does not persist. A
degraded read records empty token counts, never a fabricated figure.

### Read/render — never a second source of truth

`metrics_aggregate.py` reads only already-finalized invocations; it performs
no transcript I/O of its own and writes nothing. Panel 6 sums each
invocation's `role_usage` list directly — the `coordinator` bucket
(main-session work attributed to **the run's own skill**) surfaces exactly
like `planner`/`executor`/`verifier`/`other`, and an `unattributed` bucket
is visible rather than silently absorbed into an attributed role's total; it
also absorbs main-session records attributed to a different acs skill than
the run's own, not just records with no attribution at all.
`usage_by_model` (MAR-3) sums each invocation's `model_usage` list similarly,
at both repo and per-ticket scope. `_apply_panel6_shares` (MAR-4) computes
each panel-6 bucket's `token_share_pct` as a repo-scope percentage of the
already-summed totals, once, after the accumulation loop — never persisted,
always recomputed on the next read; `usage_by_ticket` (MAR-4) similarly
derives each role's ticket-scope share from the same per-ticket `role_usage`
rows panel 6 already sums, so it reports a different (ticket-local)
denominator, not a conflicting figure. A cost or API-duration field that an
invocation, `run.json` or `metrics.json` written before ADR 0103 still
carries is ignored, never summed or rendered.
