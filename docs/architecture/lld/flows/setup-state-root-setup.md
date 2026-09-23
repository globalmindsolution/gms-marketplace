# Flow — `/acs:setup` state-root setup

`/acs:setup` sets up the acs workspace root on every fresh run and every
re-run. The state root is always the in-repo default — there is no override
to choose ([ADR-0102](../../../adr/0102-documents-are-found-not-configured.md)) — so the skill retrofits
the in-repo state root's gitignore coverage through two independent layers,
verifies the combined result, guards against a broad ignore rule swallowing
committed CI-readable files, creates the resolved state root and checks it is writable,
and — only when a retired `workspace_path` key still points at an external
workspace left by an older acs for this repo — offers a user-confirmed, one-shot
migration into the new in-repo location. The reads are `setup detect` (Step 1)
and the writes are `setup apply` (Step 3), both in `setup_wizard.py`; the
migration offer is made at Step 1, before anything is asked. See
the companion `setup-state-root-setup.evidence.md` sidecar for the code
anchors this doc would otherwise cite inline.

## Sequence diagram

```mermaid
sequenceDiagram
    participant User
    participant Init as /acs:setup
    participant Git as git plumbing - subprocess
    participant FS as Filesystem
    participant Mig as migrate_workspace.py

    User->>Init: run /acs:setup
    Init->>Init: Step 1 - setup detect reports the workspace, ignore state and retired_keys
    opt a retired workspace_path key points at an external workspace for this repo
        Init->>User: name the key as ignored, offer to migrate that workspace into the repo
        alt user confirms
            Init->>Mig: run migrate_workspace.py with from, to, repo-root
            Mig->>Mig: preflight - no live lock, no in_progress last run
            Mig->>FS: copy old partition tree, verify, then remove old tree
            Mig-->>Init: idempotent - safe to re-run if interrupted
        else user declines
            Init-->>User: old workspace left in place, no longer read
        end
    end
    Init->>Init: Step 3 - setup apply
    Init->>Init: state root = main-checkout root + .acs/state-machine - no override
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
    Init->>Git: check-ignore -q .acs/state-machine again, after both writes
    alt combined result does not confirm the ignore
        Init-->>User: WARNING - state root is not actually ignored, check for a conflicting negation rule
    end
    Init->>Git: check-ignore -q .acs/settings.json and .acs/ci/check-conventions.py
    alt either path is swallowed by a broad rule
        Init-->>User: WARNING - narrow the rule, or CI cannot read the committed files
    end
    Init->>FS: resolve state root - default_state_root cwd
    Init->>FS: mkdir the resolved state root, then check it is writable
```

Both gitignore-coverage warnings above are non-fatal: `/acs:setup` warns
and continues rather than hard-failing, since a conflicting negation rule or a
pre-existing broad `.acs/` ignore is the user's own configuration to fix, not
something init itself can safely resolve. The migration offer only ever
triggers when a settings file still carries the retired `workspace_path` key
pointing at an external workspace left by an older acs — a directory that
already contains a partition tree for this repo; when there is none, the
branch is skipped entirely and nothing is asked.
