# 0065 — Configurable design/spec templates with byte-identical built-in defaults

**Status**: Accepted · **Date**: 2026-07-18

## Context

`create-design` and `create-spec` each hardcode the required section list their
executor writes and their verifier's structure gate checks — the six design
headings (`Context & constraints; Options considered; Decision & rationale;
Architecture; Impact & risks; Rollout/migration`) live as a literal
`<constraint name="required_sections">` in `create-design/SKILL.md`, and the
five spec headings (`Scope; Approach; API/data changes; Test plan; Out of
scope`) live inline in `create-spec/SKILL.md`. A consumer repo cannot tailor
those section shapes to its own house style the way it already can for the PR
description via `formats.pr_description_template` /
`enforcement.pr_description_sections`.

The G39 goal (PRD, MAR-149 epic design Decision C) asks for the design/spec
section shapes to be **configurable per repo**, consistent with the shipped PR
template mechanism, without changing behavior for any repo that does not
configure them. This ADR records how the two skills' section contracts become
settings-driven while the default remains exactly today's output. It is the
config/data foundation (this child, MAR-151 spec 01); the skill/verifier wiring
that consumes these keys is spec 02, and the create-spec blocking `structure`
dimension it enables is the enforcement half.

## Decision

**Mirror `pr_description_template` exactly, with an explicit `*_sections`
companion (Option C1).** Add `formats.design_template` (default
`design-default`) and `formats.spec_template` (default `spec-default`) to the
`additionalProperties:false` `formats` block — so both keys MUST be declared —
and their section companions `enforcement.design_sections` /
`enforcement.spec_sections` to the `additionalProperties:true` `enforcement`
block, exactly the way `pr_description_template` pairs with
`pr_description_sections`. Templates resolve by the same three tiers: built-in
name → `${CLAUDE_PLUGIN_ROOT}/templates/<name>.md` →
`<checkout_root>/.acs/templates/<name>.md` → absolute path (C-20
consumer-repo generality). Two built-in template files
(`plugins/acs/templates/design-default.md`, `spec-default.md`) carry the default
headings; the `## ` headings — and only the headings — are the enforcement
contract.

**Built-in defaults are byte-identical to today's hardcoded literal.** The
`enforcement.design_sections` default `;`-joins to the exact six-heading literal
in `create-design/SKILL.md`, and `enforcement.spec_sections` is the exact five
`create-spec` headings. With no `*_template` key set, create-design/create-spec
output and the structure gate are unchanged — a proven invariant, not a claimed
one (`test_configurable_doc_templates_schema.py` asserts default == the SKILL
literal, html-unescaping the `&amp;`-encoded example first). Because
`structure_lint.py` is `;`-delimited, a heading containing `&`
(`Context & constraints`) round-trips through the gate without splitting.

**The verifiers enforce the configured list as a blocking `structure`
finding.** `create-design-verifier` already runs `structure_lint.py` over the
`required_sections` it is handed; its list simply becomes the resolved
`enforcement.design_sections`. `create-spec-verifier` gains a net-new blocking
`structure` dimension over `enforcement.spec_sections` (spec 02). No change to
`structure_lint.py` itself — it is reused unchanged.

## Alternatives considered

- **Runtime template-parse (Option C2)** — derive the required sections by
  parsing the `## ` headings out of the resolved template file at run time,
  with no `*_sections` settings key. Rejected: it diverges from the shipped
  `pr_description_sections` precedent (which carries an explicit companion key),
  couples the deterministic CI checker to markdown parsing, and gives the
  consumer no place to pin the enforced list independently of the authoring
  template. The explicit companion key is the established, testable pattern.
- **Leave the section lists hardcoded** — zero new surface, but does not deliver
  the G39 configurability goal; a consumer cannot tailor the design/spec shape
  the way it already tailors the PR description. Rejected.
- **A single shared `formats.doc_template` for both skills** — fewer keys, but
  design and spec have distinct section contracts and distinct verifiers;
  one key cannot carry two different default lists. Rejected in favor of the
  per-skill pair that mirrors the existing per-artifact template keys.

## Consequences

- A repo that sets `formats.design_template` / `formats.spec_template` (and the
  matching `*_sections`) now drives the create-design/create-spec section
  contract and both verifiers' structure gate from settings, resolved the same
  way as `pr_description_template`.
- A repo that sets nothing is **byte-identical** to today: the defaults reproduce
  the prior hardcoded literals verbatim and in order, and a guard test locks
  `default == today's literal` so a future edit to either list cannot silently
  drift the two apart.
- The six-heading literal stays present in `create-design/SKILL.md` (reframed as
  the default `enforcement.design_sections` carries) so both the byte-identical
  test and readers keep a single visible source of the default shape.
- `create-spec` gains a deterministic blocking `structure` floor for the first
  time (spec 02), matching create-design; this is additive and orthogonal to the
  MAR-150 `audience-style` gate (ADR 0063) and to the MAR-152 evidence sidecar
  (ADR 0064, reserved and merging last).
- ADR number 0065 is design-assigned; 0064 is intentionally reserved for
  Decision B (MAR-152) and is absent until that child lands.
