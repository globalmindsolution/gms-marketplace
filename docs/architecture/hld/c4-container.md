# C4 Level 2 — Containers

```mermaid
C4Container
    title GMS Marketplace — containers

    Person(dev, "Developer")
    System_Boundary(mkt, "GMS Marketplace (plugin catalog)") {
        Container(skills, "acs Skills", "32 x SKILL.md", "Coordinator protocols: lifecycle, reflection loop, user interaction, completion reports")
        Container(agents, "acs Subagents", "32 x agent .md (all reachable)", "Executor + verifier pair for the twelve authoring skills (create-prd/-architecture/-project/-design, create-requirements, standardize-project, docs-sync, analyze-requirements, create-impl-plan/-api-contract/-test-docs/-e2e-tests — 24 agents; no planner, ADR 0092) plus create-docs (2); four executor-only skills — the three apply-work ones (create-ticket/-pr/merge-pr) and code, whose review left for review-code (4); and review-code's own lens + adjudicator, which fan out independently rather than pairing (2); grounding rules; JSON I/O")
        Container(hooks, "acs Hook & helper layer", "Python 3.9+ stdlib", "dispatch + 19 pre + 19 post hooks; acs (the CLI: run, step, result, ...), new-ticket, handoff, clarify, mermaid_lint, structure_lint, citation_check, prd_conformance_check, status lines; acs_lib")
        Container(schemas, "acs Schemas & templates", "JSON Schema / md", "15 JSON schemas (run, step-state, result, verdict, workflow, lock, ...), 5 description templates; templates/ci/ includes the opt-in e2e workflow+runner pair (acs-e2e.yml + run-e2e.py) alongside the tests/conventions gate templates")
    }
    System_Ext(cc, "Claude Code runtime")
    ContainerDb_Ext(ws, "Workspace store", "Filesystem", "In-repo by default: <main-checkout>/.acs/state-machine/<repo>/runs/<run-id>/ partitions (steps/, subject/) plus ticket partitions and repo-level index/counters/metrics/sessions, gitignored, anchored to the main checkout (ADR-0086); no override (ADR-0102)")
    System_Ext(repo, "Consumer repo")
    System_Ext(trackers, "GitHub / Jira")
    ContainerDb_Ext(transcript, "Claude Code transcript store", "Filesystem, ~/.claude/projects/", "Per-session JSONL transcript (message.usage token counts, model, timestamps, attribution fields) plus its own subagents/ subtree; read-only, outside the workspace store (MAR-1)")
    System_Ext(statusline_src, "statusLine cost payload", "Opt-in Claude Code stdin feed to statusline.py — a shape-agnostic total_cost_usd figure, sampled and persisted into the workspace store, never read back from Claude Code directly (MAR-1)")

    Container(tests_plugin, "tests/<plugin>/", "Python unittest", "Per-plugin deterministic tests; discovered by unittest discover -s tests")
    Container(evals_plugin, "plugins/<plugin>/evals/", "Markdown + YAML case files, run by claude plugin eval", "Per-plugin eval cases (routing, artifacts); run locally and at the release gate, NOT in CI")

    Rel(dev, cc, "/acs:*")
    Rel(cc, skills, "expands skill, runs coordinator")
    Rel(cc, hooks, "PreToolUse(Skill) -> dispatch; Stop; PreCompact; SessionEnd")
    Rel(skills, agents, "spawns via Agent tool (JSON task)")
    Rel(skills, hooks, "acs step start / post-hook / helpers (Bash)")
    Rel(agents, ws, "phase artifacts (execute/verify, lens/adjudication)")
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
Tooling containers (`tests/<plugin>/`, `plugins/<plugin>/evals/`)
are developer/CI support and sit outside the runtime boundary. The eval
cases ship inside the plugin directory — so an installed build carries
its own suite, and `claude plugin eval <plugin>@<marketplace>` can grade
what a consumer received — but nothing at runtime reads them.

**Transcript store and statusLine payload (MAR-1, ADR 0082).** Both new
external data sources are read-only from the hook layer's side — the hook
layer never writes into the transcript store, and it consumes the
statusLine payload only to sample and persist a shape-agnostic cost figure,
never to read it back. This is the read-outside-the-workspace exception
recorded in `docs/requirements/non-functional/portability.md`.
