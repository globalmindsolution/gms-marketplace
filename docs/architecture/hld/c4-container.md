# C4 Level 2 — Containers

```mermaid
C4Container
    title GMS Marketplace — containers

    Person(dev, "Developer")
    System_Boundary(mkt, "GMS Marketplace (plugin catalog)") {
        Container(skills, "acs Skills", "16 x SKILL.md", "Coordinator protocols: lifecycle, reflection loop, user interaction, completion reports")
        Container(agents, "acs Subagents", "27 x agent .md", "Planner/executor/verifier charters per hooked skill; grounding rules; XML I/O")
        Container(hooks, "acs Hook & helper layer", "Python 3.9+ stdlib", "dispatch + 9 pre + 9 post hooks; skill-start, new-ticket, handoff, clarify, validate_xml, status lines; acs_lib")
        Container(schemas, "acs Schemas & templates", "JSON Schema / XSD / md", "9 state schemas, acs-messages.xsd, 4 description templates")
        Container(tabp_skills, "tabp Skills", "1 x SKILL.md (screen-cvs)", "Screen-CV recruiting workflow; dispatched via Cowork")
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
    Rel(tests_plugin, mkt, "validates per-plugin schemas, hooks, skills presence-gated")
```

Container responsibilities are deliberately asymmetric: **skills/agents decide,
the hook layer records and gates** — no prose can unlock a gate, and no script
makes a judgment call. The marketplace boundary holds heterogeneous plugin
shapes: acs (full-shape) and tabp (skills-only). Tooling containers
(`tests/<plugin>/`, `evals/<plugin>/`) are developer/CI support and sit
outside the runtime boundary.
