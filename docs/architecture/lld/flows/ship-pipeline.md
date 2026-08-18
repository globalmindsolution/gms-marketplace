# Flow — /ship pipeline orchestration

`/ship` adds orchestration only: the coordinator invokes each step's hook-gated
flow **directly** via the Skill tool in its own context, reading a compact
`<handoff>` back; the ledger (`pipeline-state.json`) is the only memory `/ship`
needs.

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant SH as /acs:ship (coordinator)
    participant WS as pipeline-state.json
    participant SK as /acs:<step> (hook-gated flow)

    Dev->>SH: /acs:ship "Add wishlist support"  (or SHOP-123 to resume)
    SH->>WS: read ledger -> first incomplete step
    loop create-ticket -> [create-design] -> code -> [test] -> docs-sync -> create-pr
        SH->>SK: invoke Skill acs:<step> <ticket-id> directly<br/>(PreToolUse gate fires on the coordinator's call)
        SK-->>SH: full run (reflection, hooks, state) then <handoff status="..."><br/>(~1 KB: summary, artifacts, next-step)
        alt status = needs_input
            SH->>Dev: relay <questions>
            Dev-->>SH: answers
            SH->>SK: re-invoke same step directly + Q/A context<br/>(step records them in the clarification ledger)
        else status = failed
            SH-->>Dev: step, summary, partition, resume command — stop
        else completed
            SH->>WS: (already updated by the step's post-hook)
        end
        note over SH: context may be cleared/compacted here — the ledger holds the pipeline
        note over SH: full-verify lane — /ship stops after code by design, the tail resumes in a fresh session (MAR-179)
    end
    SH-->>Dev: pipeline report + "Review the PR, then /acs:merge-pr SHOP-123"
    note over Dev: /ship never invokes /acs:merge-pr — the PR is landed separately after review
```

Properties: every hook gate still fires on the coordinator's direct Skill call
(no bypass); re-running `/ship <ticket>` resumes from the ledger; epic fan-out
runs each child's pipeline independently (parallel worktrees supported).

> **NOTE (MAR-56):** The ship coordinator reads `ticket.lane` from `ticket.json` (written
> by `/create-ticket`) to determine which pipeline steps are active. The `lane` field is
> always derived from the ticket's authoritative axes (`size` × `stakes`) via
> `derive_lane(size, stakes, needs_design, type)`. This field is available in
> `pipeline-state.json` (alongside `flow`) and in `tickets-index.json` (alongside
> `needs_design`) for observability and metrics (G14/G15).
>
> **NOTE (MAR-161 — supersedes the MAR-59 fast-lane-fold note):**
> The standalone spec-authoring skill no longer exists (ADR 0066 supersedes ADR 0006). The
> `[create-design]` bracketing above is still conditional — on
> `ticket.needs_design`, independent of lane — but there is no
> bracketed spec-authoring step on any lane: `/code`'s planner self-authors the
> five-section spec content (Scope, Approach, API/data changes, Test
> plan, Out of scope) inside its plan phase on EVERY lane when
> `<partition>/specs/` is absent or empty, and reads pre-existing specs
> unchanged when they are present (backward-compat with tickets minted
> before this ADR). See `ship/SKILL.md` "Pipeline order" step 3 and
> `code/SKILL.md`'s "Spec authoring fold" section.
>
> **NOTE (MAR-159):** The pipeline also gains a new **conditional** step between
> `code` and `create-pr` — a post-code, pre-create-pr `/acs:test --for-ticket <id>`
> invocation. It is gated by `settings.post_code_test`: OFF only when neither
> `settings.e2e` nor `suites.e2e` is configured (per AC-5); ON otherwise, or
> whenever `post_code_test.enabled` is explicitly set to `true`/`false`. On
> failure the step increments `pipeline-state.json.steps.test.fix_loops`
> (capped by `post_code_test.fix_loops_cap`, default 2) and relays back into
> `/acs:code <ticket-id>` via the pipeline's existing "Re-invoke after
> needs_input" pattern — no new relay mechanism. See `ship/SKILL.md`
> "Pipeline order" and "Post-code test gate", and ADR 0068
> (`docs/adr/0068-acs-test-ticket-scoped-fix-and-retest-mode.md`).
>
> **NOTE (MAR-160):** The pipeline gains one more step, `docs-sync`, inserted
> between `code`/`test` and `create-pr` — a new hooked triad skill
> (`docs-sync-planner`/`-executor`/`-verifier`) that independently re-derives
> doc impact from `git diff <default_branch>...HEAD`, `/code`'s
> `result.json`, and the final code-verify artifact, committing any doc
> updates as additional commits on the SAME ticket branch (never a new
> branch, never a new PR). `gate_create_pr` now also requires `docs-sync`
> `completed`, alongside its existing `code` `completed` +
> `verifier_passed: true` checks. See `design.md`'s sequence diagram 1 and
> `ship/SKILL.md` "Pipeline order" / "Picking the next step".
>
> **NOTE (MAR-179):** On a full-verify lane the coordinator stops right
> after `code` completes and before the post-code test gate, ending
> `handed_off`; the remaining steps run in a fresh `/acs:ship <ticket-id>`
> resumed from `pipeline-state.json`. Light lanes are unaffected. Which
> steps run and in what order is unchanged. See `ship/SKILL.md` "Full-verify
> pipeline boundary".
