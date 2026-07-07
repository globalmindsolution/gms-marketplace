# 0043 — `suites` map generalization with soft-deprecated `e2e` alias

**Status**: Accepted · **Date**: 2026-07-07

## Context

`settings.e2e` was acs's only configured-test-command surface: a single
`{ "command", "setup"?, "teardown"?, "per_iteration"? }` block consumed by the
code-verifier and referenced by create-spec's e2e-impact rule. `/acs:test`
([ADR 0011](0011-sdlc-doc-sets-quality-and-operations.md) D6) needs to run
*multiple, independently named* test commands — unit, integration,
regression, and e2e — which a single `e2e` key cannot express. Generalizing
to a map of named suites is the natural fix, but the existing `e2e` key
already has real consumers (the code-verifier, create-spec) that must keep
working unchanged.

## Decision

`settings.suites` is the single source of truth for every configured test
command: `{ "<name>": { "command", "setup"?, "teardown"?, "per_iteration"? } }`.
`settings.e2e` is retained as a documented, soft-deprecated **compatibility
alias** — still accepted and validated exactly as before, but **normalized at
load time** into `suites["e2e"]`, so every downstream consumer (`/acs:test`,
the code-verifier, create-spec) reads suites through one resolved map rather
than two independently-consulted keys. `/acs:init` offers a one-time
`e2e` → `suites.e2e` migration on re-run (writing the new key, leaving the old
key in place unless the user opts to remove it).

**Alternative rejected: a permanent, equally-blessed `e2e` peer key
(no deprecation, no normalization).** Zero migration cost and matches the
additive/no-break pattern used for other settings additions, but leaves two
permanent, equally-valid ways to express the same suite forever, with no path
toward `suites` becoming the one canonical surface and no natural precedence
story for tooling/docs to point at long-term (R2 back-compat risk was judged
better addressed by normalizing once, upstream, than by leaving two
independently-consulted keys live indefinitely).

## Consequences

- Existing `e2e` consumers (the code-verifier, create-spec's e2e-impact rule)
  keep working unchanged — normalization happens once, in `load_settings`,
  upstream of every consumer, per the load-time-normalization design
  assumption. No consumer-repo `e2e` block stops working.
- `settings.schema.json`'s `e2e` description gains a deprecation note; its
  `required`/`properties`/`additionalProperties` shape is otherwise
  byte-identical to before this ADR.
- A configured-`e2e`-only settings file resolves to
  `result["suites"]["e2e"] == result["e2e"]` field-for-field; a repo with
  both keys set keeps `e2e` as the winning value for the `suites["e2e"]`
  entry, with no `GateError` raised on the collision.
- `/acs:init` steers consumers toward the new shape on every re-run, so drift
  toward the single canonical surface shrinks over time without a breaking
  change.
