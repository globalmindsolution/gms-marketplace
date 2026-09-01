# Flow — `/acs:initialize` state-root setup

`/acs:initialize` sets up the acs workspace root on every fresh run and every
re-run. After the default-vs-override choice is collected, the skill retrofits
the in-repo state root's gitignore coverage through two independent layers,
verifies the combined result, guards against a broad ignore rule swallowing
committed CI-readable files, creates and write-probes the resolved state root,
and — only when an existing external workspace is detected for this repo —
offers a user-confirmed, one-shot migration into the new in-repo location. See
the companion `initialize-state-root-setup.evidence.md` sidecar for the code
anchors this doc would otherwise cite inline.

## Sequence diagram

```mermaid
sequenceDiagram
    participant User
    participant Init as /acs:initialize
    participant Git as git plumbing - subprocess
    participant FS as Filesystem
    participant Mig as migrate_workspace.py

    User->>Init: run /acs:initialize
    Init->>Init: default = main-checkout root + .acs/state-machine
    Init->>User: accept the default, or set an explicit workspace_path override
    alt user accepts the default
        Init->>Init: workspace_path left unset in settings
    else user sets an explicit override
        Init->>Init: validate absolute path - expand and require isabs
        Init->>FS: write workspace_path to settings.local.json
    end
    Init->>Git: check-ignore -q .acs/state-machine
    alt not already ignored
        Init->>FS: append .acs/state-machine/ to .gitignore - tracked layer
    else already ignored
        Init->>Init: no-op - a broader existing rule already covers it
    end
    Init->>Git: rev-parse --git-common-dir
    Git-->>Init: git-common-dir path
    Init->>FS: check <git-common-dir>/info/exclude for .acs/state-machine/
    alt not already present
        Init->>FS: append .acs/state-machine/ to info/exclude - untracked layer
    else already present
        Init->>Init: no-op - idempotent
    end
    Init->>Git: check-ignore -v .acs/state-machine
    alt combined result does not confirm the ignore
        Init-->>User: WARNING - state root is not actually ignored, check for a conflicting negation rule
    end
    Init->>Git: check-ignore -q .acs/settings.json and .acs/ci/check-conventions.py
    alt either path is swallowed by a broad rule
        Init-->>User: WARNING - narrow the rule, or CI cannot read the committed files
    end
    Init->>FS: resolve state root - override if set, else default_state_root cwd
    Init->>FS: mkdir the resolved state root, write then remove a probe file
    opt an existing external workspace is detected for this repo
        Init->>User: migrate the existing external workspace into the repo now
        alt user confirms
            Init->>Mig: run migrate_workspace.py with from, to, repo-root
            Mig->>Mig: preflight - no live lock, no in_progress last run
            Mig->>FS: copy old partition tree, verify, then remove old tree
            Mig-->>Init: idempotent - safe to re-run if interrupted
        else user declines
            Init-->>User: old workspace left in place, workspace_path unchanged
        end
    end
```

Both gitignore-coverage warnings above are non-fatal: `/acs:initialize` warns
and continues rather than hard-failing, since a conflicting negation rule or a
pre-existing broad `.acs/` ignore is the user's own configuration to fix, not
something init itself can safely resolve. The migration offer only ever
triggers when an external `workspace_path` is detected pointing at a directory
that already contains a partition tree for this repo; when none is detected,
the branch is skipped entirely and nothing is asked.
