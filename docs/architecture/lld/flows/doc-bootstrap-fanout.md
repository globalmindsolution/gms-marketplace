# Flow — /acs:create-docs cross-skill fan-out

`/acs:create-docs` is an unhooked coordinator (like `/acs:ship`) that spawns
**two or more existing doc-bootstrap skills as ordinary delivery tickets**,
running each one's own plan→execute→verify phases in a **parallel worktree**,
one delivery ticket per leg. It reuses the worktree-per-ticket primitive that
already exists for cross-*ticket* parallelism; what is new is the cross-*skill*,
phase-level fan-out from a single coordinator: each phase batch (both
planners, then both executors, then both verifiers) runs in parallel before
the next batch starts. `fanout_batches()` (`acs_lib.py`) computes the eligible
batch from `DOC_BOOTSTRAP_DEPENDENCIES` and `DOC_BOOTSTRAP_SETTINGS_KEY`
against the consumer repo's settings and on-disk doc state
(`doc_set_present_on_disk()`), gated on the declared v1 set
`DOC_BOOTSTRAP_FANOUT_V1` (`create-quality`, `create-operations`).

## Sequence — happy path (both legs succeed)

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant CD as acs:create-docs (coordinator, unhooked)
    participant WS as workspace (tickets-index.json, metrics.json — repo-level)
    participant PLQ as create-quality-planner
    participant PLO as create-operations-planner
    participant EXQ as create-quality-executor
    participant EXO as create-operations-executor
    participant VFQ as create-quality-verifier
    participant VFO as create-operations-verifier

    Dev->>CD: /acs:create-docs
    CD->>WS: read settings + DOC_BOOTSTRAP_DEPENDENCIES + tickets-index.json
    CD->>CD: fanout_batches -> eligible batch = create-quality, create-operations
    CD->>CD: create worktree-Q and worktree-O outside the consumer repo

    CD->>CD: Skill acs:create-quality
    note over CD: PreToolUse(Skill) fires for real (ship/SKILL.md precedent) — cwd is the session checkout, gate_create_quality passes
    CD->>WS: skill-start.py --skill create-quality --allocate, mints MAR-101, lock, pointer, update_index — run in the session checkout (D3.2-ii)

    CD->>CD: Skill acs:create-operations
    note over CD: PreToolUse(Skill) fires for real (ship/SKILL.md precedent) — cwd is the session checkout, gate_create_operations passes
    CD->>WS: skill-start.py --skill create-operations --allocate, mints MAR-102, lock, pointer, update_index — run in the session checkout (D3.2-ii)
    CD->>WS: enter worktree-Q, git checkout -b MAR-101 (Branch step, before create-quality Execute)
    CD->>WS: enter worktree-O, git checkout -b MAR-102 (Branch step, before create-operations Execute)

    par create-quality plan
        CD->>PLQ: task phase=plan, ticket-id=MAR-101
        PLQ-->>CD: iter-1-plan.md, quality
    and create-operations plan
        CD->>PLO: task phase=plan, ticket-id=MAR-102
        PLO-->>CD: iter-1-plan.md, operations
    end

    par create-quality execute, iteration 1
        CD->>EXQ: task phase=execute, ticket-id=MAR-101
        EXQ-->>CD: docs/quality writes on MAR-101 branch, worktree-Q
    and create-operations execute, iteration 1
        CD->>EXO: task phase=execute, ticket-id=MAR-102
        EXO-->>CD: docs/operations writes on MAR-102 branch, worktree-O
    end

    par create-quality verify, iteration 1
        CD->>VFQ: task phase=verify, ticket-id=MAR-101
        VFQ-->>CD: zero blocking findings
    and create-operations verify, iteration 1
        CD->>VFO: task phase=verify, ticket-id=MAR-102
        VFO-->>CD: zero blocking findings
    end

    CD->>WS: commit + push + gh pr create in worktree-Q, post-create-quality.py, update_metrics guarded
    CD->>WS: commit + push + gh pr create in worktree-O, post-create-operations.py, update_metrics guarded
    CD-->>Dev: report, MAR-101 PR A in_review, MAR-102 PR B in_review, review each then merge-pr
```

## Sequence — one leg fails, isolation and resume

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant CD as acs:create-docs (coordinator, unhooked)
    participant WS as workspace
    participant EXO as create-operations-executor
    participant VFO as create-operations-verifier

    Dev->>CD: /acs:create-docs
    CD->>WS: Starts for MAR-101 (create-quality) and MAR-102 (create-operations) as above
    note over CD: both legs' Starts and plan phases already completed, per happy-path diagram

    par create-quality iteration 1..3
        CD->>WS: create-quality reaches zero findings, commit, push, gh pr create, post-create-quality.py
        WS-->>CD: MAR-101 in_review, PR A open
    and create-operations iteration 1..3
        CD->>EXO: task phase=execute, iteration=3
        EXO-->>CD: docs/operations writes, worktree-O
        CD->>VFO: task phase=verify, iteration=3
        VFO-->>CD: blocking findings remain at the iteration cap
        CD->>WS: create-operations-state.json run status=failed, commit to local MAR-102 branch only, no push, no PR, post-create-operations.py releases lock
    end

    CD-->>Dev: report, MAR-101 completed PR A in_review, MAR-102 failed verifier cap reached iteration 3, findings in phases/create-operations/result.json
    note over CD: no shared failure state, MAR-101's run/PR/ledger are untouched by MAR-102's failure

    Dev->>Dev: address the verifier findings
    Dev->>CD: /acs:create-operations MAR-102
    note over CD: standalone resume, unchanged contract, create-operations/SKILL.md Resume & reconcile section, reconcile=true, no re-invocation of the umbrella
    CD-->>Dev: create-operations completes, MAR-102 PR B in_review
```

Properties: each leg is an ordinary, independently-resumable delivery ticket
— its own branch, its own PR, its own verifier state; the umbrella holds no
shared failure state across legs, so one leg's iteration-cap failure never
blocks or rolls back a sibling leg's success. A crashed or failed leg resumes
exactly the way a standalone run already does, via its own skill's Resume &
reconcile path — `/acs:create-docs` is never re-invoked for a single-leg
resume. Each leg's worktree is entered at that leg's own Delivery step's
Branch sub-step, before that leg's Execute phase; that Branch entry point
precedes the later Delivery commit/push/PR steps, which run in the same
worktree once entered. The shared session checkout is used for both
legs' Starts and `skill-start.py --allocate` calls (D3.2-ii); each leg's
execute and verify phases, and Delivery steps 2-4, then run in that leg's
own worktree on its own branch.
