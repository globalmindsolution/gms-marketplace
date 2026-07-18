# C4 Level 2 — Containers

```mermaid
C4Container
    title GMS Marketplace — containers

    Person(dev, "Developer")
    System_Boundary(mkt, "GMS Marketplace (plugin catalog)") {
        Container(skills, "acs Skills", "24 x SKILL.md", "Coordinator protocols: lifecycle, reflection loop, user interaction, completion reports")
        Container(agents, "acs Subagents", "45 x agent .md (39 reachable)", "Planner/executor/verifier triad for the twelve triad-keeping skills (create-prd/-architecture/-project/-quality/-operations/-principles/-standards/-design/-spec/code/standardize-project/create-requirements); the three apply-work skills (create-ticket/-pr/merge-pr) run inline with at most one executor, no planner/verifier — their 6 plan/verify agent files are orphaned; grounding rules; XML I/O")
        Container(hooks, "acs Hook & helper layer", "Python 3.9+ stdlib", "dispatch + 15 pre + 15 post hooks; skill-start, new-ticket, handoff, clarify, validate_xml, mermaid_lint, structure_lint, status lines; acs_lib")
        Container(schemas, "acs Schemas & templates", "JSON Schema / XSD / md", "9 state schemas, acs-messages.xsd, 6 description templates; templates/ci/ now includes the opt-in e2e workflow+runner pair (acs-e2e.yml + run-e2e.py) alongside the tests/conventions gate templates")
        Container(tabp_skills, "tabp Skills", "2 x SKILL.md (screen-cvs, /tabp:usage)", "Screen-CV recruiting workflow; coordinator orchestrates parallel Sonnet-per-CV subagents + Opus synthesis via the coordinator+subagents convention; dispatched via Cowork or Claude Code")
        Container(tabp_agents, "tabp Subagents", "3 x agent .md", "Three reusable tabp-namespaced agent charters under plugins/tabp/agents/: screen-cv-subagent (Sonnet, one per CV) + synthesis-subagent (Opus, once per run) + screen-verifier-subagent (Sonnet, independent verifier, always-on). Spawned by the screen-cvs coordinator. No foreign-namespace tokens.")
        Container(tabp_helper, "tabp_helper.py", "Python 3.9+ stdlib only", "stdlib-only Python >= 3.9 helper; atomic .tabp/ writes, spin-lock, schema validation, run-history, usage aggregation (MAR-38); invoked via Bash; no acs import")
    }
    System_Ext(cc, "Claude Code runtime")
    System_Ext(cowork, "Cowork runtime")
    ContainerDb_Ext(ws, "Workspace store", "Filesystem", "<workspace>/<repo>/<ticket>/ partitions + repo-level index/counters/metrics/sessions")
    System_Ext(repo, "Consumer repo")
    System_Ext(trackers, "GitHub / Jira")

    Container(tests_plugin, "tests/<plugin>/", "Python unittest", "Per-plugin deterministic tests; discovered by unittest discover -s tests")
    Container(evals_plugin, "evals/<plugin>/", "Python, run_evals.py", "Per-plugin behavioral evals; run locally only, NOT in CI")

    Rel(dev, cc, "/acs:*")
    Rel(cc, skills, "expands skill, runs coordinator")
    Rel(cc, hooks, "PreToolUse(Skill) -> dispatch; SessionEnd")
    Rel(skills, agents, "spawns via Agent tool (XML task)")
    Rel(skills, hooks, "skill-start / post-hook / helpers (Bash)")
    Rel(agents, ws, "phase artifacts (plan/execute/verify)")
    Rel(hooks, ws, "state files, ledger, locks, index, metrics")
    Rel(agents, repo, "executors edit source/docs on ticket branch")
    Rel(skills, trackers, "gh / acli (sync, PRs)")
    Rel(skills, schemas, "validate messages & state; render templates")
    Rel(tabp_skills, cowork, "screen-cvs skill dispatched via Cowork")
    Rel(tabp_skills, cc, "screen-cvs / /tabp:usage dispatched via Claude Code")
    Rel(tabp_skills, tabp_agents, "spawns screen-cv-subagent per CV + synthesis-subagent once per run")
    Rel(tabp_skills, tabp_helper, "run-start / state-write / decision-write / run-finalize / run-status (Bash)")
    Rel(tabp_helper, ws, ".tabp/ state: run.json, evidence, decision, history, lock")
    Rel(tests_plugin, mkt, "validates per-plugin schemas, hooks, skills presence-gated")
```

Container responsibilities are deliberately asymmetric: **skills/agents decide,
the hook layer records and gates** — no prose can unlock a gate, and no script
makes a judgment call. The marketplace boundary holds heterogeneous plugin
shapes: acs (full-shape) and tabp (skills + helper + schemas + subagent charters).
Tooling containers (`tests/<plugin>/`, `evals/<plugin>/`) are developer/CI support
and sit outside the runtime boundary.
