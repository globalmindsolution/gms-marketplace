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
