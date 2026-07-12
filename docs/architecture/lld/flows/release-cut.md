# Flow — cut-release

A developer runs `/acs:release <version>`; the coordinator probes idempotency
first, then drafts and dates the CHANGELOG section from the merged-ticket
archive, bumps both manifests + `source.ref`, and opens an exempt `release/*`
PR — stopping for a mandatory human merge before the existing `release.yml`
workflow tags and publishes. Transcribed verbatim from the binding design
(`MAR-128/design.md` "Sequence diagrams" → "Flow — cut-release").

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant Rel as "/acs:release coordinator (unhooked)"
    participant Lib as "acs_lib.build_context"
    participant RN as "release_notes.py"
    participant Arc as "workspace archive"
    participant Chg as "CHANGELOG.md"
    participant Man as "marketplace.json + plugin.json"
    participant Gh as "gh CLI"
    participant Wf as "release.yml (CI)"

    Dev->>Rel: /acs:release 0.4.2
    Rel->>Lib: build_context(cwd)
    Lib-->>Rel: settings, workspace_path, repo_id
    Rel->>RN: release_notes.py status --version 0.4.2
    RN->>Man: read current version, source.ref
    RN->>Gh: gh pr list --head release/v0.4.2
    RN->>Gh: gh api ...tags/v0.4.2 (existence check)
    RN-->>Rel: manifests_at_target, changelog_section_dated, open_pr, tag_exists

    alt already at target and PR open (idempotent re-run)
        Rel-->>Dev: no-op — report existing release/v0.4.2 PR, nothing to do
    else tag already exists
        Rel-->>Dev: no-op — v0.4.2 already released
    else fresh cut
        Rel->>RN: release_notes.py draft --version 0.4.2
        RN->>Arc: enumerate archive tickets merged since v0.4.1
        RN->>Chg: read [Unreleased]
        RN->>RN: draft section, cross-check coverage
        RN-->>Rel: draft_section, coverage report
        Rel-->>Dev: show coverage report, N merged, M covered, K missing
        Rel->>RN: release_notes.py bump --version 0.4.2
        RN->>Chg: write dated section, retain empty [Unreleased]
        RN->>Man: bump both versions, set source.ref = v0.4.2
        RN-->>Rel: files_changed, ok
        Rel->>Gh: git checkout -b release/v0.4.2, commit, push
        Rel->>Gh: gh pr create --label ACS (release/* exempt branch)
        Gh-->>Rel: PR number, url
        Rel-->>Dev: STOP — PR ready for human review, reminds paid-eval gate
    end

    Note over Dev,Gh: human reviews and edits the drafted section as needed
    Dev->>Gh: gh pr merge release/v0.4.2 (human action)
    Gh->>Wf: push to main touches marketplace.json
    Wf->>Wf: tag-exists guard — false, proceed
    Wf->>Chg: extract "## [0.4.2]" section verbatim
    Wf->>Wf: git tag -a v0.4.2, git push origin v0.4.2
    Wf->>Gh: gh release create v0.4.2 --notes-file
    Wf-->>Dev: v0.4.2 tagged and published
```

Composes with [`ticket-lifecycle.md`](ticket-lifecycle.md) for the PR that
precedes a release (every ticket merged since the last tag is the population
`release_notes.py draft` enumerates from the archive).
