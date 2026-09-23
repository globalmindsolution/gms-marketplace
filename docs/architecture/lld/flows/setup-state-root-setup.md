# Flow — `/acs:setup` state-root setup

`/acs:setup` sets up the acs workspace root on every fresh run and every
re-run. The state root is always the in-repo default — there is no override
to choose ([ADR-0102](../../../adr/0102-documents-are-found-not-configured.md)) — so the skill retrofits
the in-repo state root's gitignore coverage through two independent layers,
verifies the combined result, guards against a broad ignore rule swallowing
committed CI-readable files, creates the resolved state root and checks it is writable,
and names any retired settings key still in a settings file as ignored. The
reads are `setup detect` (Step 1) and the writes are `setup apply` (Step 3),
both in `setup_wizard.py`. See the companion `setup-state-root-setup.evidence.md`
sidecar for the code anchors this doc would otherwise cite inline.

Setup is optional, and nothing depends on this flow having run
([ADR-0105](../../../adr/0105-acs-runs-without-setup.md)): the state root
ignores itself, because the first state write under it creates
`.acs/state-machine/.gitignore` containing `*`. The two layers below are
kept for a repo that runs setup, not needed by one that never does.

## Sequence diagram

```mermaid
sequenceDiagram
    participant User
    participant Init as /acs:setup
    participant Git as git plumbing - subprocess
    participant FS as Filesystem

    User->>Init: run /acs:setup
    Init->>Init: Step 1 - setup detect reports the workspace, ignore state and retired_keys
    opt a settings file still carries a retired key
        Init->>User: name the key and its file, say it is ignored
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
something init itself can safely resolve. Moving state that an older acs kept
in an external workspace is not part of setup: `migrate_workspace.py` does it
by hand ([workspace-and-state.md](../../../requirements/functional/workspace-and-state.md)).
