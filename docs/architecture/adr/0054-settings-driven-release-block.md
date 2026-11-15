# 0054 — Settings-driven `release` block (JSON-manifest-focused schema, Option A); marketplace = profile #1

**Status**: Accepted · **Date**: 2026-07-12

## Context

C-20 explicitly deferred the `release` block's exact schema shape to this
design phase, naming this marketplace as configured profile #1. The shipped
`release_notes.py` (pre-amendment) hardcoded six of this marketplace's own
artifacts — `_marketplace_path()` → `.claude-plugin/marketplace.json`,
`_plugin_path()` → `plugins/acs/.claude-plugin/plugin.json`, `bump()`'s acs
`source.ref` write, `_changelog_path()` → `plugins/acs/CHANGELOG.md`,
`since_tag()`'s `git describe --tags --abbrev=0 main`, and
`tag_exists()`/`release_branch()`/`gh_pr_list()`'s `v%s`/`release/v%s`
literals — a live violation of C-20 and Principle 1 (consumer-repo
generality) recorded against this exact skill.

## Decision

`plugins/acs/schemas/settings.schema.json` gains an OPTIONAL, non-secret
`release` object sub-schema — JSON-manifest-focused `{file, pointer}`
`version_locations[]` + typed `extra_refs[]` (a name-match selector, not a
brittle array index) + `changelog_path` + `tag_format` + `base_branch` +
`release_branch_format` + `publish_driver` (Option A). `release_notes.py`
reads the block via a single `--release-config <json>` CLI flag instead of
hardcoding this marketplace's paths. This marketplace's own
three-manifest-plus-CHANGELOG edit is committed as `release` profile #1 in
this repo's own `.acs/settings.json`, reproduced byte-for-byte (R-A2
regression test).

## Alternatives considered

- **Option B — format-agnostic `{file, kind: json-pointer|regex|line}`.**
  Fuller generality across ecosystems; *rejected for this pass*: no
  non-JSON consumer exists in this repo today, and regex-driven writes are
  riskier than structured JSON edits, in tension with the atomic-write
  safety story. Option A's optional per-entry `kind` field, defaulting to
  `json-pointer`, makes Option B a strictly additive future extension, not
  a schema rewrite.
- **Option C — command-driven `bump_command`/`publish_command`.**
  *Rejected outright*: collides with Principle 4's stdlib-only,
  runtime-agnostic core and the Portability NFR, is an
  arbitrary-code-execution surface, and breaks the atomic-write + four-signal
  idempotency guarantees the unhooked-utility shape depends on.

## Consequences

- `settings.schema.json` gains its first new top-level property for this
  epic — this reverses the original (pre-amendment) design's own claim that
  "no settings schema change" was needed for either MAR-129 or MAR-130
  capability.
- No secret/credential field is ever added (mirrors the `tracker` "no
  secrets in settings" NFR).
- A repo with no `release` key configured cannot run `/acs:release` — it
  fails fast (`release_notes.py` exits 2, no write), never a silent
  marketplace-hardcoded fallback (Security NFR (v)).
- ADRs 0050-0053 (the unhooked shape, archive-authoritative draft,
  human-merge gate, roadmap-mapping-table decoupling) are all unaffected —
  only the artifact-location mechanism changes, not the decisions those
  four ADRs record.
