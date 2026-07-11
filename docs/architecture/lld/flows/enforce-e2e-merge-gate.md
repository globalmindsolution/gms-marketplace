# Flow — enforce-e2e-merge-gate

A red e2e suite becomes a fail-closed merge brake; a green one lets
`/acs:merge-pr`'s existing `ci` readiness dimension pass. Transcribed verbatim
from the binding design (`MAR-124/design.md` Flow 1).

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant GH as GitHub (PR)
    participant WF as acs-e2e.yml workflow
    participant RUN as run-e2e.py
    participant BP as Branch protection (required check)
    participant MP as /acs:merge-pr (readiness read)

    Dev->>GH: open or update PR (opened, reopened, synchronize)
    GH->>WF: trigger acs-e2e.yml for the PR head SHA
    WF->>RUN: python3 .acs/ci/run-e2e.py
    RUN->>RUN: read committed .acs/settings.json, resolve suites e2e or the e2e alias
    RUN->>RUN: run setup, if configured
    RUN->>RUN: run command, the e2e suite
    RUN->>RUN: run teardown, always, in a finally block
    RUN-->>WF: exit status equals command's status
    WF-->>GH: report E2E suite check conclusion for the head SHA
    GH->>BP: evaluate required status checks
    alt e2e check red, suite failed or runner error
        BP-->>GH: mergeStateStatus BLOCKED, PR cannot merge
        Dev->>MP: /acs:merge-pr TICKET-ID, any time
        MP->>GH: gh pr checks --required, gh pr view mergeStateStatus
        MP-->>Dev: readiness ci fail, protections fail, report-only stop
    else e2e check green
        BP-->>GH: required check satisfied, mergeable pending other checks
        Dev->>MP: /acs:merge-pr TICKET-ID
        MP->>GH: gh pr checks --required, gh pr view mergeStateStatus
        MP-->>Dev: readiness ci pass, proceeds toward merge if all four dimensions pass
    end
```

Composes with [`ticket-lifecycle.md`](ticket-lifecycle.md) for the surrounding
PR lifecycle, and with [`standardize-project.md`](standardize-project.md) for
the brownfield-scaffold-only sibling path (E2E-2/MAR-126, out of scope here).
