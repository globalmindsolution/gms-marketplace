# /acs:code — lane changes during a run

*Read by the /acs:code coordinator on demand; it is not loaded with
SKILL.md. Path: `${CLAUDE_PLUGIN_ROOT}/skills/code/references/lane-changes.md`.*

The lane (TRIVIAL / SMALL / STANDARD / COMPLEX) is derived from the ticket's
`size` and `stakes` axes, and it sets the reflection loop's iteration ceiling
and verify depth. Most runs never change it: the lane resolved at Start is the
lane the run finishes on, and the coordinator never opens this file.

Read this file when one of these is true, and only then — it is two
conditional branches, not part of the main flow:

| Situation | Section |
|---|---|
| A verifier finding, a `high_stakes_paths` match, or an explicit request suggests this ticket is bigger or higher-stakes than it was classified | [In-loop escalation check](#in-loop-escalation-check-upward-only-mar-57) |
| The user asks, at an iteration or run boundary, to LOWER size/stakes | [Boundary-only user-confirmed de-escalation](#boundary-only-user-confirmed-de-escalation-d3) |

The through-line across all three: **rigor is raised freely and lowered only
with a recorded human confirmation.** An automatic path may escalate on its own
evidence, because being too careful costs time; only a person may de-escalate,
because being too careless costs correctness, and `confirm_deescalation` is the
one sanctioned lowering path in the system.

---

### In-loop escalation check (upward-only, MAR-57)

At the **start of each iteration** — after the verifier for the previous
iteration has run and before launching the current iteration's execute phase —
evaluate three upward-escalation triggers. Completed iterations are NEVER
discarded; escalation continues from the current point at higher rigor WITHOUT
restarting the run (AC-1 / no-restart guarantee).

**This is the iteration-start escalation detection point (MAR-107 D4).**
Because `verify_depth`/ceiling re-selection happens before the current
iteration's execute, an escalation always lands **before the next verifier
pass** — the verifier for the just-finished iteration has already run, and the
verifier for the upcoming iteration has not, so the ticket cannot merge
without a passing verifier at the escalated depth (`states.verifier_passed`
merge gate). The no-restart guarantee above (completed work preserved,
without restarting the run) holds at this same detection point.

**Three triggers (exactly; no others) — evaluated on the FIRST signal, immediately.**
This signal set is normatively frozen at exactly these three triggers: no
fourth trigger exists or may be added without a new design decision. Trigger
(b) is the **sole deterministic, unit-tested** signal; triggers (a) and (c)
remain coordinator **judgment** paths, contract-tested as prose. "Larger
scope" (file/spec-count growth) has no dedicated deterministic helper this
release — it folds into triggers (a)/(c).

**(a) Verifier finding signaling higher stakes/size.** The coordinator inspects
the verifier's findings for any item whose dimension is "Architecture & system
design", "Security", or "Business logic" and whose text indicates the touched
surface is higher-stakes or larger than currently classified. No new structured
verifier field is added (reuse existing finding signals only). The coordinator
applies judgment over finding text; the deterministic path is trigger (b).

**(b) `high_stakes_paths` glob matched mid-implementation.** After the execute
phase writes files, the coordinator calls `recommend_stakes(changed_paths,
settings)` (`acs_lib/lanes.py`) over the iteration's changed file set — as
`acs.py stakes recommend --paths-from -`, fed the iteration's full changed
set:

```bash
# Bind the anchor first: a bare <default-branch> here is parsed by bash as a
# REDIRECTION, so that command is skipped, the other two still emit, and the
# pipeline still exits 0 -- a partial path set that can under-trigger.
default_branch="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||')"
{ git diff --name-only "${default_branch:?set it first}"...HEAD
  git diff --name-only HEAD
  git ls-files --others --exclude-standard; } \
  | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" stakes recommend --paths-from -
```

All three anchors, because the execute phase COMMITS its work (step 5 below) and
the trigger is evaluated after it: `git diff --name-only HEAD` alone sees only
uncommitted edits to tracked files, so by then a newly added `auth/session.py` —
exactly the path the trigger exists to catch — is invisible in every one of the
three states it can be in. The `<default-branch>...HEAD` form is the same anchor
the verify step uses; the other two cover work not yet committed. A return value
of `"high"` fires trigger (b). Stakes is then raised to `"high"` for the new
axes. This is the deterministic, fully unit-testable trigger; it reuses the
`high_stakes_paths` setting mechanism — no re-implementation.

**(c) Explicit user/agent escalation request.** Any in-flight message from the
user, the coordinator, or any subagent (executor or verifier) may carry an
explicit escalation request. Any subagent may RAISE rigor; none may lower it.
The coordinator recognizes a request as explicit only when it unambiguously
states a higher lane or axis value.

**On-trigger escalation sequence (when any trigger fires):**

Steps 1-2 and 4b-4f are one command — run it rather than reimplementing the
sequence in ad-hoc Python (ADR 0001):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" lane apply \
  --ticket <ticket-id> [--proposed-size <size>] [--proposed-stakes <stakes>] \
  --trigger <a|b|c> [--source "<what the signal said>"]
```

It performs the steps below in exactly the order they are written, and prints
`{ticket_id, from_lane, lane, size, stakes, depth, ceiling_before,
ceiling_after, escalated, event_recorded, event}`. On the no-op branch it adds
`reason` plus `proposed_size`/`proposed_stakes`, and `lane`/`size`/`stakes` then
report what is ON DISK — nothing was written, so a caller must not read the
proposal back as a raise. `event` is always present, null when none was
recorded.
The prose that follows is the contract that command implements — read it to
understand what the command guarantees, not as an instruction to hand-roll it.

1. Determine new axes via `guard_axes(current_size, current_stakes, proposed_size,
   proposed_stakes)` (`acs_lib/lanes.py`). `guard_axes` returns `(effective_size,
   effective_stakes)` by taking the higher of each axis — it is the axis-level
   realization of the negative guarantee (design.md:29 invariant (e)):
   no automatic/unattended path can write a `size` or `stakes` value that is
   strictly lower than the currently confirmed value (AC-3). For trigger (b) the
   proposed stakes is `"high"`; for trigger (a)/(c), pass the axis value the
   signal indicates. Call `guard_axes` BEFORE `escalate_lane`.
2. Call `escalate_lane(current_lane, eff_size, eff_stakes, needs_design,
   ticket_type)` (`acs_lib/lanes.py`) to obtain `(new_lane, new_depth, new_ceiling)`.
   Lane is never hand-set — `derive_lane` inside `escalate_lane` is the single
   authoritative producer (ADR 0030).
3. If `new_lane == current_lane` (no raise needed): no-op, continue.
4. If `new_lane` is strictly higher (per `lane_rank`):
   a. Update the in-memory ticket object's `size`, `stakes`, and `lane` fields.
      An axis the ticket does not have and nobody proposed stays ABSENT: it is
      not materialised at `guard_axes`'s floor, which would let a rigor-raising
      path write the lowest possible value and anchor every later comparison.
   b. Persist to `ticket.json` via `save_ticket(tdir, ticket)` — writes the new
      axes and `lane`.
   c. Persist to `pipeline-state.json` via `update_pipeline(tdir, ticket_id,
      "code", "in_progress", lane=new_lane)`.
   d. Persist to `tickets-index.json` via `update_index(workspace, repo_id,
      ticket)`.
   e. Raise the in-flight iteration ceiling to `max(current_ceiling,
      new_ceiling)` — monotone raise only, never lower an already-higher
      ceiling (AC-1/AC-7).
   f. **After** steps b-e above (never before, never interleaved), construct
      the 13-field escalation event (`ts, from_lane, to_lane, from_size,
      from_stakes, to_size, to_stakes, trigger, source, ceiling_before,
      ceiling_after, direction, confirmation_ref`) with `direction: "up"` and
      `confirmation_ref: null`, and call `record_escalation_event(tdir, "code",
      event)` (`acs_lib/state.py`) to durably persist it to `runs[-1].escalations` on
      `code-state.json`. This ordering makes an audit-write failure detectable:
      the axes/lane are already durably applied by b-d, so a lane change with
      no matching event is itself the signal, rather than an event recorded for
      a persistence that never completed. Idempotency on resume: escalation
      fires only on the FIRST signal per trigger detection (line above); a
      resumed `/code` run re-reads the already-escalated `ticket.lane`/`size`/
      `stakes` from `ticket.json`, so `guard_axes`/`escalate_lane` recompute a
      no-op (step 3 above short-circuits) and `record_escalation_event` is
      never reached a second time for the same already-applied escalation — no
      duplicate event is appended.

**Absent or ambiguous signals — no-op (AC-7 conservative default):**
When none of the three triggers fires in an iteration, the coordinator makes no
axis or lane changes. Unrecognized or ambiguous signals (e.g. a verifier finding
that mentions security but concludes the surface is within scope) do not trigger
escalation — the coordinator must observe an unambiguous signal. A ticket stays
at its current lane when in-flight signals are absent, ambiguous, or
unrecognized; the lane is never lowered.

**Non-epic COMPLEX breakdown recommendation on mid-flight escalation (D7-C).**
When the on-trigger sequence above (step 2, `escalate_lane`) yields
`new_lane == "COMPLEX"` for this non-epic ticket, surface — never block —
the same breakdown recommendation as the Start step: note the axes that
produced `COMPLEX` and suggest promoting the ticket to an epic and running
`/acs:create-design`, then continue the run at the escalated verify depth.
This recommendation is a report attached to the existing three-trigger
sequence's outcome — it is never a fourth trigger, and it never causes
automatic de-escalation; the lane stays upward-only.

---

### Boundary-only user-confirmed de-escalation (D3)

De-escalation (lowering `size`/`stakes`/lane) is offered **ONLY** at an
iteration or run boundary of `/acs:code` — the point where the reflection loop
is between iterations, or the run itself is between invocations — and
**NEVER** mid-iteration. No other boundary definition applies.

When a user requests de-escalation at a boundary, the coordinator follows this
confirmation sequence, in order, before any write:

1. Record the question via `clarify.py add` (unanswered).
2. Issue an explicit `AskUserQuestion` asking the user to confirm the lower
   `size` and/or `stakes` value.
3. Only on an explicit affirmative reply, record the answer via `clarify.py
   answer`, yielding a `C-<n>` id. No write to `ticket.json`/
   `pipeline-state.json`/`tickets-index.json` happens before this confirmation
   round-trip completes.
4. Call `confirm_deescalation(tdir, ticket, confirmed_size, confirmed_stakes,
   clarify_ref=C-<n>)` (`acs_lib/state.py`), passing the resolved `C-<n>` ledger id
   as `clarify_ref` — as `acs.py lane deescalate --ticket <id> --size <size>
   --stakes <stakes> --clarify-ref C-<n>`, which refuses unless the ref resolves
   to an *answered* entry.

   **Exit 2 does not by itself mean nothing was written.** `confirm_deescalation`
   persists `ticket.json`, `pipeline-state.json` and the index *before* recording
   its audit event, so read stdout: an ordinary refusal prints nothing, while
   `applied: true, event_recorded: false` means the lowering is durable and only
   its audit event is missing. That state needs a human, not a retry. This subsection references the writer by its exact name
   and signature only — the writer's internal behavior (lane recompute,
   persistence order, event recording) is its own contract, unchanged here.

`confirm_deescalation` is the **only sanctioned lane-lowering path** in the
system. It is called from **exactly this one location** in `code/SKILL.md`,
and it is **never** called from the in-loop trigger-evaluation code path (the
three-trigger check above) and **never** from any subagent (executor,
verifier, or any spawned planner).

This subsection does not introduce an automatic or unattended downgrade path:
de-escalation never happens automatically, and there is no automatic path that
lowers the lane or axes — every downgrade mention here stays inside this
user-confirmed, boundary-gated sequence, and `confirm_deescalation` cannot be
reached without a resolved, answered `clarify_ref`.
