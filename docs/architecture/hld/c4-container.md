# C4 Level 2 — Containers

```mermaid
C4Container
    title GMS Marketplace — containers

    Person(dev, "Developer")
    System_Boundary(mkt, "GMS Marketplace (plugin catalog)") {
        Container(skills, "acs Skills", "28 x SKILL.md", "Coordinator protocols: lifecycle, reflection loop, user interaction, completion reports")
        Container(agents, "acs Subagents", "31 x agent .md (all reachable)", "Executor + verifier pair for the twelve authoring skills (create-prd/-architecture/-project/-design, create-requirements, standardize-project, docs-sync, analyze-ticket, create-impl-plan/-api-contract/-test-docs/-e2e-tests — 24 agents; no planner, ADR 0092); executor + verifier pairs for code and create-docs (ADR 0089, ADR 0094; 4 agents); the three apply-work skills (create-ticket/-pr/merge-pr) run inline with at most one executor, no verifier (3 agents — their plan/verify files were deleted under ADR 0092); grounding rules; XML I/O")
        Container(hooks, "acs Hook & helper layer", "Python 3.9+ stdlib", "dispatch + 15 pre + 15 post hooks; skill-start, new-ticket, handoff, clarify, validate_xml, mermaid_lint, structure_lint, citation_check, prd_conformance_check, status lines; acs_lib")
        Container(schemas, "acs Schemas & templates", "JSON Schema / XSD / md", "9 state schemas, acs-messages.xsd, 6 description templates; templates/ci/ now includes the opt-in e2e workflow+runner pair (acs-e2e.yml + run-e2e.py) alongside the tests/conventions gate templates")
    }
    System_Ext(cc, "Claude Code runtime")
    ContainerDb_Ext(ws, "Workspace store", "Filesystem", "In-repo by default: <main-checkout>/.acs/state-machine/<repo>/<ticket>/ partitions + repo-level index/counters/metrics/sessions, gitignored, anchored to the main checkout (ADR-0086); an explicit workspace_path override may point elsewhere")
    System_Ext(repo, "Consumer repo")
    System_Ext(trackers, "GitHub / Jira")
    ContainerDb_Ext(transcript, "Claude Code transcript store", "Filesystem, ~/.claude/projects/", "Per-session JSONL transcript (message.usage token counts, model, timestamps, attribution fields) plus its own subagents/ subtree; read-only, outside the workspace store (MAR-1)")
    System_Ext(statusline_src, "statusLine cost payload", "Opt-in Claude Code stdin feed to statusline.py — a shape-agnostic total_cost_usd figure, sampled and persisted into the workspace store, never read back from Claude Code directly (MAR-1)")

    Container(tests_plugin, "tests/<plugin>/", "Python unittest", "Per-plugin deterministic tests; discovered by unittest discover -s tests")
    Container(evals_plugin, "src/acs-evals/behavioural/<plugin>/", "Python, run_evals.py", "Per-plugin behavioral evals; run locally only, NOT in CI")

    Rel(dev, cc, "/acs:*")
    Rel(cc, skills, "expands skill, runs coordinator")
    Rel(cc, hooks, "PreToolUse(Skill) -> dispatch; SessionEnd")
    Rel(skills, agents, "spawns via Agent tool (XML task)")
    Rel(skills, hooks, "skill-start / post-hook / helpers (Bash)")
    Rel(agents, ws, "phase artifacts (plan/execute/verify)")
    Rel(hooks, ws, "state files, ledger, locks, index, metrics")
    Rel(agents, repo, "executors edit source/docs on ticket branch")
    Rel(skills, trackers, "gh / acli (sync, PRs) -- critical calls stop the run, incl. gate-input reads whose failure leaves a readiness gate unevaluable; metadata calls degrade to findings and continue (ADR-0088)")
    Rel(skills, schemas, "validate messages & state; render templates")
    Rel(tests_plugin, mkt, "validates per-plugin schemas, hooks, skills presence-gated")
    Rel(hooks, transcript, "usage_reader.py reads the run's exact recorded transcript_path + subagents/, read-only, never a constructed path (MAR-1)")
    Rel(cc, statusline_src, "pipes a JSON payload (model, workspace, session, cost) to statusline.py on every refresh")
    Rel(hooks, statusline_src, "cost_sampler.py samples the real cost figure and persists it into the workspace store (MAR-1)")
```

Container responsibilities are deliberately asymmetric: **skills/agents decide,
the hook layer records and gates** — no prose can unlock a gate, and no script
makes a judgment call. The marketplace boundary holds heterogeneous plugin
shapes (ADR 0021); acs (full-shape) is the one plugin published today.
Tooling containers (`tests/<plugin>/`, `src/acs-evals/behavioural/<plugin>/`)
are developer/CI support and sit outside the runtime boundary.

**Transcript store and statusLine payload (MAR-1, ADR 0082).** Both new
external data sources are read-only from the hook layer's side — the hook
layer never writes into the transcript store, and it consumes the
statusLine payload only to sample and persist a shape-agnostic cost figure,
never to read it back. This is the read-outside-the-workspace exception
recorded in `docs/requirements/non-functional/portability.md`.
