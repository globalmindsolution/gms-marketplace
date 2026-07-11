# Flow — /acs:standardize-project audit → scaffold → additive-only verify

The most safety-critical flow in the epic (D6). Modeled on the standard
hook-gated triad (`hook-gated-skill-run.md`) with the additive-only gate
made explicit at the verify phase.

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant CC as Claude Code
    participant SP as /acs:standardize-project (coordinator)
    participant PL as standardize-project-planner
    participant EX as standardize-project-executor
    participant VF as standardize-project-verifier
    participant Repo as Consumer repo (checkout_root)

    Dev->>CC: /acs:standardize-project
    CC->>SP: PreToolUse(Skill) gate fires, skill-start allocates ticket
    SP->>PL: <task phase="plan"> audit inputs: standards_path,<br/>principles_path, hld/project-structure.md, readiness tooling
    PL-->>SP: plan — gap list (docs/config/tooling missing),<br/>structural-gap candidates, additive-surface allowlist
    SP->>EX: <task phase="execute"> scaffold ONLY the allowlisted gaps
    EX->>Repo: add missing docs/config/CI files (never edit/rename/delete existing source)
    EX-->>SP: execute report — files added, structural gaps deferred to report
    SP->>VF: <task phase="verify">
    VF->>Repo: git diff --name-status base...HEAD (re-run independently)
    alt any R (rename) or D (delete) status, or M outside allowlist
        VF-->>SP: blocking finding — additive-only violation, exact path + status
        SP->>PL: loop back (re-plan or re-scope), up to 3 iterations
    else all statuses are A within the allowlist
        VF-->>SP: zero findings — additive-only guarantee holds
        SP->>Repo: open PR — docs/config/tooling only,<br/>recommended_follow_ups listed in the PR body
        SP-->>Dev: completion report — 1 reviewed PR, 0 source relocations
    end
```

Contract: the verifier never trusts the executor's self-report — it re-runs
`git diff --name-status` itself every iteration, mirroring how every other
acs verifier re-runs cheap checks rather than trusting recorded claims
(`code-verifier.md:9-11` "you never rubber-stamp... trust nothing recorded").

**E2E-2 delta note.** When `settings.e2e`/`suites.e2e` is set and
`.github/workflows/acs-e2e.yml` is missing, the executor's "add missing
docs/config/CI files" step (above) additionally scaffolds `acs-e2e.yml` +
`run-e2e.py` — reused verbatim from E2E-1's committed
`plugins/acs/templates/ci/` pair — under the SAME allowlist categories 1
("New CI workflow file(s)") + 2 ("…e2e runner scaffold config") this diagram
already governs. No new diagram, no new participant: the existing sequence
above already models this exact step. `/acs:standardize-project` never wires
branch protection itself; that stays with `/acs:init`.
