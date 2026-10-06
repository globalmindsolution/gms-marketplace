# C4 Level 2 — Containers

```mermaid
C4Container
    title GMS Marketplace — containers

    Person(dev, "Developer")
    System_Boundary(mkt, "GMS Marketplace (plugin catalog)") {
        Container(skills, "acs Skills", "29 x SKILL.md", "Coordinator protocols: lifecycle, reflection loop, user interaction, completion reports")
        Container(agents, "acs Subagents", "34 x agent .md (all reachable)", "Roles named for each skill's own work, each of kind survey, write or judge (ADR 0109): a writer + judge pair for the eleven authoring skills (create-prd/-architecture/-design/-data-design/-flows, docs-sync, analyze-requirements, create-impl-plan/-api-contract/-test-docs/-e2e-tests), with a surveyor for create-prd, an impact analyst for analyze-requirements and a gap analyst for create-architecture, create-api-contract, create-data-design and create-flows (28 agents); code's implementer (1); review-code's lens + adjudicator, which fan out independently rather than pairing (2); audit-design's read-only gap analyst (1, ADR-0122); audit-security's auditor + adjudicator, a survey per category and a refute-by-default judge per candidate finding, no writer (2, ADR-0123); the apply-work skills (create-ticket/-pr/merge-pr) run inline and own none; grounding rules; JSON I/O")
        Container(hooks, "acs Hook & helper layer", "Python 3.9+ stdlib", "dispatch + 19 pre + 19 post hooks; acs (the CLI: run, step, result, handoff, ...), new-ticket, handoff (the session pause), clarify, mermaid_lint, structure_lint, citation_check, prd_conformance_check; acs_lib")
        Container(schemas, "acs Schemas & templates", "JSON Schema / md", "13 JSON schemas (run, step-state, result, verdict, workflow, lock, ...), 7 description templates (PR, epic/story/task, design, and the audit-design and audit-security report templates, ADR-0123); templates/ci/ includes the opt-in e2e workflow+runner pair (acs-e2e.yml + run-e2e.py) alongside the tests/conventions gate templates")
    }
    System_Ext(cc, "Claude Code runtime")
    ContainerDb_Ext(ws, "Workspace store", "Filesystem", "In-repo by default: <main-checkout>/.acs/state-machine/<repo>/runs/<run-id>/ partitions (steps/, subject/) plus ticket partitions and repo-level index/counters/sessions, gitignored, anchored to the main checkout (ADR-0086); written through acs.py, never the Write tool (ADR-0136); no override (ADR-0102)")
    System_Ext(repo, "Consumer repo")
    System_Ext(trackers, "GitHub")

    Container(tests_plugin, "tests/<plugin>/", "Python unittest", "Per-plugin deterministic tests; discovered by unittest discover -s tests")
    Container(evals_plugin, "plugins/<plugin>/evals/", "Markdown + YAML case files, run by claude plugin eval", "Per-plugin eval cases (routing, artifacts); run locally and at the release gate, NOT in CI")

    Rel(dev, cc, "/acs:*")
    Rel(cc, skills, "expands skill, runs coordinator")
    Rel(cc, hooks, "PreToolUse(Skill) -> dispatch; Stop; PreCompact; SessionEnd")
    Rel(skills, agents, "spawns via Agent tool (JSON task)")
    Rel(skills, hooks, "acs step start / post-hook / helpers (Bash)")
    Rel(agents, ws, "phase artifacts (per-role reports, lens/adjudication)")
    Rel(hooks, ws, "state files, ledger, locks, index")
    Rel(agents, repo, "write roles edit source/docs in the working tree, uncommitted")
    Rel(skills, trackers, "gh (sync, PRs) -- critical calls stop the run, incl. gate-input reads whose failure leaves a readiness gate unevaluable; metadata calls degrade to findings and continue (ADR-0088)")
    Rel(skills, schemas, "validate messages & state; render templates")
    Rel(tests_plugin, mkt, "validates per-plugin schemas, hooks, skills presence-gated")
```

Container responsibilities are deliberately asymmetric: **skills/agents decide,
the hook layer records and gates** — no prose can unlock a gate, and no script
makes a judgment call. The marketplace boundary holds heterogeneous plugin
shapes (ADR 0021); acs (full-shape) is the one plugin published today.
Tooling containers (`tests/<plugin>/`, `plugins/<plugin>/evals/`)
are developer/CI support and sit outside the runtime boundary. The eval
cases ship inside the plugin directory — so an installed build carries
its own suite, and `claude plugin eval <plugin>@<marketplace>` can grade
what a consumer received — but nothing at runtime reads them.

**No transcript store (ADR 0104).** The Claude Code transcript store that
token measurement read is no longer a container here: acs records no usage
and reads no transcript
([ADR 0104](../adr/0104-no-usage-dashboards-no-usage-recording.md)). The
hook layer's only input from Claude Code is the hook envelope.
