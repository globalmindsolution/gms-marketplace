# Flow — GitHub call failure policy (criticality classification)

`gh` is acs's **sole** GitHub transport in every environment (ADR-0088; no
GitHub MCP fallback, clarification C-6 of epic MAR-401). Every in-scope `gh`
call site across `create-ticket/SKILL.md`, `create-pr/SKILL.md`, and
`merge-pr/SKILL.md` is classified into one of four disposition classes:
**critical** (gh's verbatim stderr plus one canonical
`acs_lib.gh_failure_hint()` hint, then stop — no silent fallback to any
other transport); **critical per ticket, soft per batch** (an error-severity
finding for that one item, but the batch continues — `create-ticket/
SKILL.md`'s `gh issue create` tracker-sync call); **non-critical** (one
`info` finding plus a replayable `gh` command block, never abort); or
**loud-but-non-reverting** (an error-severity finding naming the outstanding
sync, but an already-completed action — such as a merge — is never reverted
or re-attempted). The classes are defined by consequence, not by
write-versus-read: a gate-input read whose failure leaves a readiness gate
unevaluable is critical, because an unevaluable gate is never treated as
passed (`hld/overview.md:30`).

## Sequence — one gh call site, all four classes, and the post-merge exception

```mermaid
sequenceDiagram
    autonumber
    participant SK as Apply-work skill coordinator
    participant SH as Bash
    participant GH as gh CLI
    participant RES as Result document plus phase artifact

    SK->>SH: run one gh command for operation OP
    SH->>GH: exec
    GH-->>SH: exit code, stdout, stderr
    alt exit code is 0
        SH-->>SK: success payload
        SK->>RES: record outcome, continue to the next step
    else non-zero and OP is CRITICAL
        note over SK,RES: critical writes -- gh pr create/edit, gh issue view on import, gh pr merge (merge-pr/SKILL.md Step 1 Merge and the exempt-mode site)
        note over SK,RES: critical gate-input reads -- gh pr list, gh repo view for base, merge-pr gh pr view / gh pr checks --required, gh pr update-branch
        SK->>SK: hint = acs_lib.gh_failure_hint(stderr)
        SK->>RES: error finding -- gh stderr verbatim plus the one hint sentence, replayable false
        note over SK,RES: for a gate-input read, the readiness gate becomes unevaluable -- never treated as passed (hld/overview.md:30)
        SK-->>SK: STOP the run, no later step executes -- for merge-pr this is before Step 1 Merge, never after
    else non-zero and OP is gh issue create (create-ticket Step 5 tracker sync, one ticket)
        note over SK,RES: hybrid disposition -- critical per ticket, soft per batch
        SK->>SK: hint = acs_lib.gh_failure_hint(stderr)
        SK->>RES: error finding -- that ticket's id plus gh stderr verbatim plus the one hint sentence, replayable false, surfaced in errors
        SK-->>SK: the batch continues to the next ticket -- only this ticket's external stays null, no full-run stop
    else non-zero and OP is NON-CRITICAL
        note over SK,RES: metadata -- labels, assignee, milestone, Projects v2, CODEOWNERS reviewers, PR back-reference comment, gh run list CI diagnostic read
        SK->>SK: hint = acs_lib.gh_failure_hint(stderr)
        SK->>RES: info finding -- command, verbatim error, hint, replayable true
        SK->>SH: continue with the next operation
    end
    opt merge-pr Step 2 Cleanup post-merge tracker sync fails
        note over SK,RES: loud-but-non-reverting -- Step 1 Merge already landed, the merge is never reverted or re-attempted
        SK->>RES: error-severity finding naming the outstanding sync, plus a replayable gh command block
        note over SK,RES: the run still finishes merged true
    end
```

## merge-pr's two merge sites carry the identical rule

`### Step 1 — Merge` (`merge-pr/SKILL.md`, gated only when all Step 0
readiness dimensions pass or Step 1a's BEHIND carve-out succeeds) and
`## Exempt non-ticket PR mode` (the `gh pr merge` call reached via the
sanctioned `/acs:merge-pr --pr <PRNUMBER>` path named in `CLAUDE.md`) run the
identical critical rule at the identical command: verbatim stderr + the
canonical hint, stop **before** `### Step 2 — Cleanup` ever runs. Step 2's
own tracker sync (`gh issue close`, Projects Status→Done) is the one
loud-but-non-reverting exception in this policy: by the time Step 2 runs, the
merge in Step 1 has already landed, so a Step-2 failure is reported — never
grounds to revert or re-attempt the merge — and the run still finishes
`merged: true`.
