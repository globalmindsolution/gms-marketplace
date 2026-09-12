# 0068 — `/acs:test` ticket-scoped fix-and-re-test mode

**Status**: Accepted · **Date**: 2026-07-30

## Context

Epic MAR-155's design D5 ("Where does the e2e post-code loop live") decided
that `/acs:ship` should gain a conditional, post-code/pre-create-pr test
step that exercises a ticket's own changes (including its e2e suite, when
configured) before the PR opens, and loops a failure back into `/acs:code`
for a bounded number of attempts. Two placements were considered: a new,
parallel skill dedicated to this loop, or extending `/acs:test`'s
already-shipped suite-execution core with a scoped invocation mode
(Option B). Option B was chosen: it reuses Steps 1-3 of `/acs:test`
(argument resolution, per-suite setup→command→teardown, results-artifact
write) unmodified, avoiding a second suite-runner mechanism.

The standing `/acs:test` invocation's failure path drives a closed
regression-ticket loop (mint-or-bump-or-recur, ADR 0044). That loop exists
for failures discovered against already-merged code, where a failure is a
genuine regression deserving its own tracked ticket. A failure inside a
not-yet-merged ticket's own fix-and-re-test loop is different: it belongs
to the ticket currently in flight, not to a new standing regression ticket.
Conflating the two would double-book the same failure (design.md Risk R2,
the single highest-priority correctness requirement for this decision).

## Decision

1. `/acs:test` gains a `--for-ticket <id>` invocation mode. It resolves the
   ticket's partition, narrows the suite run set to the reserved `e2e` key
   plus any suite named in the ticket's own folded Test-plan (read from
   `<partition>/phases/code/plan.md`), and reuses Steps 1-4 exactly as the
   standing mode runs them.
2. In this mode, a failure **unconditionally** skips Steps 4a-4b (triage,
   regression-key derivation, dedup/mint-or-bump/comment-bump) — no
   condition re-enables them. Instead, the mode returns a compact verdict
   object, `{"status": "pass"|"fail", "failure_output": "..."}`, in
   addition to writing the same results artifact. ADR 0044's mint/bump/recur
   policy is **unchanged** for standing-mode runs; only this new
   ticket-scoped mode bypasses it, and only for the current, in-flight
   ticket's own failures.
3. `/acs:ship` gains a conditional post-code, pre-create-pr `test` step
   that invokes `/acs:test --for-ticket <ticket-id>` and reads its verdict:
   - `pass` → the pipeline advances to `create-pr`.
   - `fail`, with a new bounded `pipeline-state.json.steps.test.fix_loops`
     counter still under the cap (`settings.post_code_test.fix_loops_cap`,
     default `2`, independent of `/code`'s own internal iteration cap) →
     increment the counter and relay the failure into `/acs:code
     <ticket-id>` via the **existing** "Re-invoke after needs_input" relay
     pattern — not a new relay mechanism — then loop back to the test step.
   - `fail`, cap reached → stop the pipeline, mirroring the existing
     failed-handling shape.
4. A new `settings.post_code_test` block gates the step: `enabled`
   (`boolean|null`, default `null`) — an explicit `true`/`false` always
   wins; otherwise the step is **OFF only when neither `settings.e2e` nor
   `suites.e2e` is configured, ON whenever either is** — preserving PRD
   G13's e2e-gating guarantee without requiring an opt-in step the operator
   could forget to add.
5. `/acs:test`'s self-description is amended: the "not a hooked pipeline
   skill" claim now scopes explicitly to the default/standing invocation,
   since `--for-ticket` mode is invoked as one step inside `/acs:ship`'s own
   hooked pipeline walk. The skill itself still gains no pre/post hooks of
   its own, no skill-start ticket allocation, and no planner/executor/
   verifier triad in either mode.

## Consequences

**Positive consequence:** a ticket's own e2e/test failures are caught and
looped back into `/code` before a PR opens, without duplicating the
suite-execution mechanism or double-booking a failure as both a fix-loop
iteration and a spurious standing regression ticket (R2).

**Accepted cost:** `/acs:ship` takes on a small, explicit orchestration
responsibility — reading/writing the `steps.test` ledger entry itself,
since `/acs:test` has no post-hook of its own to do it. This is bookkeeping,
not step-work: the suite execution and verdict computation stay entirely
inside `/acs:test`'s own Steps 1-3.

**No change to standing-mode behavior:** the default `/acs:test` invocation
(no `--for-ticket`) is byte-for-byte unchanged — same suite selection, same
Step 4a-4b triage/dedup policy, same completion report shape.

## Amendment — skills-independence refactor (ADR-0089)

Both halves of this ADR survive; both are now declared rather than coded into
`/acs:ship`'s prose.

**The skill is renamed.** `/acs:test` becomes `/acs:run-e2e-tests`. The old
directory is kept for one release as an alias that forwards to it, listed
under `aliases` in `workflows/phases.yaml` and never in a phase; both are
unhooked. `pipeline-state.json` retains `test` beside `run-e2e-tests` in its
step enum so a pre-rename ledger still validates and the workflow walk still
finds a `steps.test` entry when resolving the renamed step.

**The post-code fix-and-retest loop is a `ship.yaml` declaration.** The
`run-e2e-tests` step carries `args: "--for-ticket {ticket_id}"`,
`when: post_code_test_active` and
`on_fail: {relay_to: code, max_loops: post_code_test_fix_loops_cap}`. The
semantics are the ones this ADR decided, unchanged: the gate is OFF only when
neither `settings.e2e` nor `suites.e2e` is configured, ON otherwise, with
`post_code_test.enabled` overriding explicitly; a failure increments the step's
`fix_loops` counter, capped by `post_code_test.fix_loops_cap` (default 2), and
relays back into `/acs:code`. What changed is that a reader learns this by
reading one file instead of inferring it from a skill's prose, and that a
consumer can retune it in its own `.acs/workflows/ship.yaml` without forking
the skill.

**The ticket-scoped mode's suite scoping gained a first source.** A
`--for-ticket` run now reads the ticket's suites from `test-cases.md` when the
ticket has one, falling back to today's folded Test-plan section; the triage
skip and the `{status, failure_output}` verdict are unchanged. Context,
Decision and Consequences above are otherwise unedited.
