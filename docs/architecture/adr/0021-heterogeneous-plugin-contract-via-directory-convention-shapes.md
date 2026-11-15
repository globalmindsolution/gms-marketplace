# 0021 — Heterogeneous plugin contract via directory-convention shapes

**Status**: Accepted · **Date**: 2026-06-18

## Context

The GMS Marketplace now hosts more than one plugin. Plugins differ in shape: acs
is a full-shape plugin with `.acs/`, `schemas/`, `hooks/`, and `agents/`
directories alongside `skills/`; tabp is a skills-only plugin with
`skills/screen-cvs/` only — no `.acs/`, `schemas/`, `hooks/`, or `agents/`. CI
must apply each check only when the directory it targets is present, so that a
skills-only plugin passes green without carrying directories it does not need
(design `MAR-26/design.md:127-129`, `65-68`).

## Options considered

**2A. By-directory convention (chosen):** CI/runners probe the filesystem — a
check runs for a plugin if and only if the directory it targets is non-empty
(e.g. `glob plugins/<p>/schemas/*.schema.json`,
`os.path.isdir("plugins/<p>/hooks")`). Matches the existing `if not paths: FAIL`
guard pattern already in `ci.yml` (e.g. lines 141-144, 207-211 for acs). Zero
new manifest surface; nothing to keep in sync; new plugins "just work";
consistent with the existing conditional idiom. Cons: shape is implicit — a
missing directory is indistinguishable from a forgotten one (not a real gap: no
check currently requires tabp to have schemas/hooks).

**2B. Explicit per-plugin manifest field:** A `shape` or `capabilities` field in
`plugin.json` or the marketplace entry; CI reads it to decide checks. Intent is
explicit and auditable. Cons: new schema surface to define, validate, and
maintain; risk of drift between declared field and reality; not part of the
Claude Code `plugin.json` spec — requires a custom key.

## Decision

Adopt **2A (by-directory convention)**. The one invariant required regardless of
plugin shape is a valid `plugin.json` whose `name` matches the marketplace entry
key — this is a hard check in the per-entry validator (MAR-29). No other
directory absence is a shape violation for skills-only plugins. Option 2B would
add a custom schema field with no real enforcement gap that 2A does not cover.
The existing `if not paths: ...` guards in `ci.yml` (lines 141-144, 207-211)
already implement this pattern (design `MAR-26/design.md:213-219`, `260-264`).

## Consequences

New plugins are added to the marketplace registry by providing a `plugin.json`
with a matching `name`; CI shape checks apply automatically based on which
directories are present. Full-shape plugins (with `.acs/`, `schemas/`, `hooks/`,
`agents/`) continue to be validated by all existing checks. Skills-only plugins
(with `skills/` only) pass CI green without carrying empty directories. The
pattern is open for extension: if a future plugin shape introduces a directory
convention that requires a new check, that check is conditioned on directory
presence in `ci.yml` without modifying any manifest schema. One deliberate
trade-off: a forgotten directory is indistinguishable from a plugin that never
had it; the test suite under `tests/<plugin>/` is the backstop for structural
correctness within each plugin's layout.
