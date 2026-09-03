# C4 Level 1 — System Context

```mermaid
C4Context
    title GMS Marketplace — system context

    Person(dev, "Developer", "Invokes /acs:* skills; answers clarifications; reviews and merges PRs")

    System(mkt, "GMS Marketplace", "Curated plugin catalog hosting heterogeneous plugins: acs (full-shape, agentic delivery workflow via Claude Code) and tabp (fuller shape: skills + helper + schemas + subagent charters + .tabp/ state, screen-CVs recruiting workflow via Cowork)")

    System_Ext(cc, "Claude Code", "Runtime: executes skills/agents, fires hook events, spawns subagents (acs targets Claude Code)")
    System_Ext(cowork, "Cowork", "Runtime: executes Cowork skills (tabp targets Cowork for screen-cvs)")
    System_Ext(repo, "Consumer repository", "Any git repo: source, tests, docs/product, docs/architecture")
    System_Ext(ws, "Workspace folder", "In-repo by default (.acs/state-machine, gitignored, main-checkout-anchored); optionally external via a workspace_path override — per-repo/ticket pipeline state, locks, metrics")
    System_Ext(gh, "GitHub", "PRs (gh CLI, acs's sole GitHub transport -- ADR-0088), optional Projects v2 tracker, marketplace distribution")
    System_Ext(jira, "Jira", "Optional tracker (acli CLI), two-way ticket sync")

    Rel(dev, cc, "types /acs:* commands, answers questions")
    Rel(cc, mkt, "loads skills/agents, fires PreToolUse / SessionEnd hooks")
    Rel(mkt, cowork, "tabp screen-cvs skill dispatched via Cowork")
    Rel(mkt, repo, "reads code/docs; /code edits source on ticket branches")
    Rel(mkt, ws, "all pipeline state: tickets, states, ledger, locks, metrics")
    Rel(mkt, gh, "push branch, open/merge PR; sync issues/Projects")
    Rel(mkt, jira, "two-way ticket sync (optional)")
```

Trust boundaries: the marketplace plugins never store credentials — `gh` and
`acli` own authentication. No second GitHub transport is sanctioned
(ADR-0088): `gh` remains the only GitHub credential holder in every
environment. The workspace defaults to an in-repo, gitignored
folder anchored to the repo's main checkout, so every linked worktree
resolves to the same physical state (ADR-0086) — worktree-sharing survives
via that anchoring, not via a fully separate machine-local folder;
cross-machine handoff is still out of scope (see PRD).
