# HLD — Data model (workspace state)

All entities are JSON files under `<workspace>/<repo-id>/`; schemas ship with
the plugin (`plugins/acs/schemas/`). Pretty-printed, atomically written,
human-auditable.

```mermaid
erDiagram
    REPO_PARTITION ||--o{ TICKET : contains
    REPO_PARTITION ||--|| TICKETS_INDEX : "indexes all tickets"
    REPO_PARTITION ||--|| COUNTERS : "id sequence"
    REPO_PARTITION ||--|| METRICS : "aggregates"
    REPO_PARTITION ||--o{ SESSION_POINTER : "one per checkout/worktree"
    TICKET ||--o{ SKILL_STATE : "one per skill that ran"
    TICKET ||--|| PIPELINE_STATE : "step ledger"
    TICKET ||--o| CLARIFICATIONS : "Q&A ledger"
    TICKET ||--o| LOCK : "held while worked"
    TICKET ||--o{ PHASE_ARTIFACT : "execute/verify per iteration; plan per iteration for the eight non-/code non-/docs-sync non-/create-project non-/standardize-project triad skills"
    TICKET ||--o{ TICKET : "epic -> children (both directions)"
    SKILL_STATE ||--|{ RUN_ENTRY : "append-only"
    TICKET ||--o| PLAN_APPROVAL : "at most one per approved plan digest, /acs:code STANDARD/COMPLEX only, written solely by plan-approval.py"
    TICKET ||--o| PLAN : "exactly one phases/code/plan.md, authored once per run before the loop"
    PLAN ||--o{ PLAN_SUPERSEDED : "one plan-superseded-<k>.md per revocation; byte-identical copy, never deleted"

    TICKET {
        string id PK "SHOP-123"
        string title
        enum type "epic|story|task"
        string description
        array acceptance_criteria
        enum priority "critical|high|medium|low"
        string parent FK "epic id or null"
        array children
        enum status "open|in_progress|in_review|done"
        json external "tracker mapping or null"
        string assignee
        number story_points
        bool needs_design "true for epics only; always false for story/task (MAR-76)"
        bool docs_only
        string due_date "ISO-8601 date or null (NEW, MAR-8 Child 3)"
        enum size "trivial|small|standard|large (axis for derive_lane; MAR-56)"
        enum stakes "low|normal|high (axis for derive_lane; MAR-56)"
        enum lane "TRIVIAL|SMALL|STANDARD|COMPLEX (derived cache from size x stakes via derive_lane; MAR-56)"
    }
    SKILL_STATE {
        string skill PK
        string ticket_id FK
        json states "canonical keys per skill; code's states.plan_approved is the first key written by a script (plan-approval.py) rather than the skill's own post-hook or coordinator — MAR-73, slice 3 of MAR-69; see INTERNALS.md's canonical-keys table"
        array findings
        array errors
    }
    PLAN_APPROVAL {
        string ticket_id FK
        string skill "code"
        enum lane "STANDARD|COMPLEX (recomputed, never cached ticket.lane)"
        datetime approved_at
        bool eligible
        string plan_path "relative to the ticket partition"
        string plan_sha256 "digest of the approved plan.md bytes"
        json predicate "function, inputs, checks, failures — acs_lib.plan_approval_eligible's verdict"
        string writer "plan-approval.py (sole writer, never a subagent or the coordinator)"
    }
    RUN_ENTRY {
        datetime started_at
        datetime ended_at
        json tokens "input/output"
        number cost_usd
        enum status "in_progress|completed|failed|interrupted|handed_off"
        string stop_reason
        string handoff_summary "when handed_off"
    }
    PIPELINE_STATE {
        string ticket_id PK
        enum flow "ticket|product"
        json steps "per-skill status/timestamps/summary"
        json totals "runs, seconds, tokens, cost"
        string lane "TRIVIAL|SMALL|STANDARD|COMPLEX (mirror of ticket.lane; written by update_pipeline; not declared in schema, allowed via additionalProperties)"
    }
    CLARIFICATIONS {
        string ticket_id PK
        array clarifications "C-n: question, answer, source, status, rationale"
    }
    LOCK {
        string checkout_id
        int pid
        string hostname
        datetime created_at
    }
    SESSION_POINTER {
        string checkout_id PK
        string ticket_id
        string skill
    }
    PLAN {
        string path "phases/code/plan.md — the only name, every lane"
        string author "code-planner on STANDARD/COMPLEX; coordinator on TRIVIAL/SMALL (MAR-72)"
        string sha256 "digest the PLAN_APPROVAL record pins"
    }
    PLAN_SUPERSEDED {
        int k "smallest positive integer with no existing file"
        string path "phases/code/plan-superseded-<k>.md"
        string writer "coordinator, at an iteration/run boundary, on a clarify.py-recorded user answer"
        string semantics "byte-identical cp of the revoked plan.md — never a rename/move; existing iter-<n>-verify.md plan.md:<line> citations resolve unchanged"
        bool approval_input "false — never an approval input, never a conformance contract (dimension 15's plan_path condition)"
    }
```

**PHASE_ARTIFACT note (MAR-70, amended by MAR-71 slice 1b; label narrowed by
MAR-74 slice 4, by MAR-300, by MAR-301 and by MAR-302).** The `"execute/verify
per iteration; plan per iteration for the eight non-/code non-/docs-sync
non-/create-project non-/standardize-project triad skills"` cardinality above already carves out
`/acs:code`'s plan leg. `/acs:code`'s plan artifact is
a single per-ticket `phases/code/plan.md`, written **exactly once per run**,
before the loop, so `/acs:code` has one plan artifact per ticket regardless of
iteration count (never rewritten in place on a later iteration — MAR-71,
slice 1b of MAR-69; this covers the `plan` leg of the ER label above for
`/acs:code`); `phases/code/plan-superseded-<k>.md` is a real, written-and-read
artifact of the plan-revocation path (MAR-74, slice 4 of MAR-69 — see the
Amendment below).
Modelling this precisely — a `PLAN` / `PLAN_APPROVAL` / `PLAN_SUPERSEDED`
entity block and a narrowed `PHASE_ARTIFACT` relationship label — is owned by
MAR-69 slices 3/4; this note records the gap without pre-empting that edit.

**Amendment (MAR-73, slice 3 of MAR-69).** The `PLAN_APPROVAL` half of the
gap above is now modelled: the `PLAN_APPROVAL` entity block and its
`TICKET ||--o| PLAN_APPROVAL` relationship above are the real artifact
behind it, written solely by `plan-approval.py` on STANDARD/COMPLEX. `PLAN`
and `PLAN_SUPERSEDED` — and the narrowed `PHASE_ARTIFACT` relationship label
covering them — remain unwritten and unread, and stay owned by **slice 4**.

**Amendment (MAR-74, slice 4 of MAR-69).** The `PLAN` / `PLAN_SUPERSEDED`
half of the gap left owned by **slice 4** above is now modelled: the `PLAN`
and `PLAN_SUPERSEDED` entity blocks and their `TICKET ||--o| PLAN` /
`PLAN ||--o{ PLAN_SUPERSEDED` relationships above are the real artifacts
behind them, and the `PHASE_ARTIFACT` relationship label is narrowed
accordingly. This corrects the MAR-73 Amendment's "remain unwritten and unread" —
`plan.md` is the plan artifact modelled by `PLAN` (unchanged since MAR-70/71),
and `plan-superseded-<k>.md`, modelled by `PLAN_SUPERSEDED`, is now written by
the coordinator at a revocation boundary and read by nothing as an approval
input or conformance contract (ADR 0073).

**Amendment (MAR-300).** `/acs:docs-sync`'s plan artifact,
`phases/docs-sync/iter-1-plan.md`, now has the same "exactly one per run,
authored before the loop, never rewritten in place on a later iteration"
cardinality as `/acs:code`'s `plan.md` above — this closes the E2 edge the
code-planner recorded (ADR-0012). Unlike `/acs:code`, `/acs:docs-sync` keeps
the `iter-<n>-plan.md` **name** (`n` is always 1, since the plan phase runs
exactly once) and carries **no** `PLAN_APPROVAL` / `PLAN_SUPERSEDED`
semantics — no new entity block is added for it; the cardinality change is
captured entirely by the narrowed `PHASE_ARTIFACT` relationship label above.

**Amendment (MAR-301).** `/acs:create-project`'s plan artifact,
`phases/create-project/iter-1-plan.md`, now has the same "exactly one per
run, authored before the loop, never rewritten in place on a later
iteration" cardinality as `/acs:code`'s `plan.md` and `/acs:docs-sync`'s
`iter-1-plan.md` above. Like `/acs:docs-sync`, `/acs:create-project` keeps
the `iter-<n>-plan.md` **name** (`n` is always 1, since the plan phase runs
exactly once) and carries **no** `PLAN_APPROVAL` / `PLAN_SUPERSEDED`
semantics — no new entity block is added for it; the cardinality change is
captured entirely by the narrowed `PHASE_ARTIFACT` relationship label above.

**Amendment (MAR-302).** `/acs:standardize-project`'s plan artifact,
`phases/standardize-project/iter-1-plan.md`, now has the same "exactly one
per run, authored before the loop, never rewritten in place on a later
iteration" cardinality as `/acs:code`'s `plan.md`, `/acs:docs-sync`'s and
`/acs:create-project`'s `iter-1-plan.md` above. Like `/acs:docs-sync` and
`/acs:create-project`, `/acs:standardize-project` keeps the
`iter-<n>-plan.md` **name** (`n` is always 1, since the plan phase runs
exactly once) and carries **no** `PLAN_APPROVAL` / `PLAN_SUPERSEDED`
semantics — no new entity block is added for it; the cardinality change is
captured entirely by the narrowed `PHASE_ARTIFACT` relationship label above.
Zero migration: no new state key, no new schema field, no new artifact path.

Invariants (enforced by `acs_lib` + schemas + tests):

- `runs[-1]` is the only source of current status — nothing mirrored at top level.
- Epic ↔ child links stored in **both** directions; epic status auto-managed.
- Cross-partition writes limited to the defined parent-epic updates; reads
  (e.g. a child consuming the epic's `design.md`) are allowed.
- Done partitions move to `archive/` — never deleted; the index keeps them.

---

## tabp plugin data model

Source: `MAR-2/specs/01-tabp-state-json-schemas.md`, `MAR-1/design.md:652-722`.
Schemas: `plugins/tabp/schemas/`. All entities live in `<project>/.tabp/`
within the Cowork project folder (separate from the acs workspace partition).

```mermaid
erDiagram
    TABP_PROJECT ||--o{ TABP_RUN : "run history (append-only)"
    TABP_PROJECT ||--|| TABP_HISTORY : "history.json"
    TABP_RUN ||--o{ EVIDENCE_RECORD : "one per candidate screened"
    TABP_RUN ||--o| DECISION_RECORD : "created at sign-off"
    TABP_RUN ||--|| XLSX_SCORECARD : "cv-screening-scorecard-<role>-<date>.xlsx"
    TABP_PROJECT ||--o| TABP_SETTINGS : "tabp settings.json"
    TABP_PROJECT ||--o| TABP_LOCK : "held during active run"

    TABP_PROJECT {
        string project_folder PK "Cowork project folder path"
    }
    TABP_HISTORY {
        string project_folder FK
        array runs "append-only array of run summaries"
    }
    TABP_RUN {
        string run_id PK "run-<ISO8601>"
        string skill "screen-cvs"
        datetime started_at
        datetime ended_at
        enum status "in_progress|completed|failed|interrupted"
        string stop_reason
        enum state_write_mode "helper|instructed"
        string usage_source "cowork|claude-code|estimate|unavailable"
        number tokens_in "null if unavailable"
        number tokens_out "null if unavailable"
        number cost_usd "null if unavailable"
        string cost_basis "actual|estimate|unavailable (optional; absent = unavailable)"
        number duration_seconds
        number candidates_screened
        string jd_slug
        string scorecard_file
    }
    EVIDENCE_RECORD {
        string run_id FK
        string candidate_id PK
        string candidate_name
        array requirements "judgment+evidence per requirement"
        number score
        string band "Strong|Moderate|Weak"
        string recommendation "Recommend|Hold|Reject"
        string must_have_gate "OK|Missing:<list>"
        bool fairness_check_passed
        array bias_flags
    }
    DECISION_RECORD {
        string run_id PK,FK
        bool verification_passed
        string verification_notes
        datetime presented_at
        object sign_off "null until recruiter confirms"
    }
    XLSX_SCORECARD {
        string run_id FK
        string filename "cv-screening-scorecard-<role>-<date>.xlsx"
    }
    TABP_SETTINGS {
        string project_folder FK
        string screening_model
        string synthesis_model
        string cv_folder
        string jd_folder
        enum state_write_mode "helper|instructed"
    }
    TABP_LOCK {
        string project_folder FK
        int pid
        string hostname
        datetime created_at
    }
```

Invariants (enforced by `tabp_helper.py` at runtime, not by schema alone):

- `runs[-1]` in `history.json` is the current status of the most recent run.
- `status = "in_progress"` means the run is resumable from `.tabp/runs/<run-id>/`.
- Evidence records and the decision record are appended/updated only within an `in_progress` run.
- The lock is held while `status = "in_progress"`; stale locks are reported, not stolen.
- No entry in `history.json` or any per-run file is ever deleted; archives are never purged.

PII-minimal rule: `candidate_name` holds only a name or anonymised label. No contact
details, no protected-class attributes, no secrets in any state file
(`design.md:129-132`).
