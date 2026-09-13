# 0093 — One declaration per contract: derive the message validator from the XSD, type the delegation keys, and declare the state a state machine actually holds

**Status**: Proposed · **Date**: 2026-09-13

## Context

Three contracts govern how acs's parts talk to each other: `acs-messages.xsd`
for agent **communication**, the `<constraints>` payload for **delegation**, and
`skill-state.schema.json` / `pipeline-state.schema.json` for the **state
machines**. Each was audited against what the shipped skills, agents and hook
scripts actually emit and read.

### Communication — structurally complete, declared twice

The message vocabulary is in good shape on its face. All twenty elements the
XSD declares are used in shipped prose; no element or attribute is emitted that
the XSD does not declare. Nothing is missing.

What is wrong is that the contract exists **twice**. `validate_xml.py` is, by
its own docstring, "a pure stdlib (`xml.etree`) structural validator raised to
XSD-equivalent coverage": it re-implements the schema as Python tables —
`ALLOWED_ATTRS`, `CHILD_ORDER`, `REQUIRED_CHILDREN`, `TEXT_LEAVES`, `PHASES`,
`RESULT_STATUSES`, `HANDOFF_STATUSES`, `VERIFY_LENSES` — under the comment
*"Keep in sync with the XSD when it changes."*

That instruction has already failed once. The XSD declared `result/@lens`; the
validator's closed attribute model rejected it, so a message the schema called
valid was refused in practice until the validator was patched by hand on
2026-09-13. Two declarations of one contract do not drift *if* someone
remembers; the defect is the remembering.

The audit also turned up the other half of that same feature: **`result/@lens`
is declared, now accepted, and emitted by nothing.** The lens reaches a
verifier as `<constraint name="verify_lens">A</constraint>` and the result
attribute that was to carry it back was never wired into any agent's prose. One
fact, two encodings, one of them dead.

### Delegation — a typed envelope around an untyped payload

Every parameter a coordinator hands a subagent — `verify_lens`, `e2e_command`,
`e2e_setup`, `standards_path`, the coverage target, the declared file map —
travels as `<constraint name="...">value</constraint>`, and the schema says:

```xml
<xs:attribute name="name" type="xs:string" use="required"/>
```

An open string. The envelope is validated; the payload is not. A misspelled
constraint name passes validation cleanly and arrives at the receiving agent as
*absent*, which every agent has a defined behaviour for — it takes its
absent-branch and proceeds. There is no failure, no error, and nothing to
notice: a delegation that lost a constraint looks exactly like one that was
never given it. Nor can the schema express that a given task *requires* a
particular constraint.

### State machines — strong where recently touched, blank elsewhere

`skill-state.schema.json` declares 53 paths, and the recently-added ones are
declared thoroughly: `runs[].guard_events` is specified field by field
(`ts`, `skill`, `iteration`, `tool`, `target`, `reason`, `declared_count`).

Two things it does not declare at all:

- **`runs[].escalations`** — `record_escalation_event` appends a documented
  13-field event to it on every lane escalation, and it is the durable audit
  trail ADR-0092's predecessor relies on. The schema has no mention of it. The
  newer `guard_events` was explicitly modelled *on* escalations, and only the
  copy got declared.
- **`states`** — a bare `object` with no properties. The code writes at least
  `plan_approved`, `pr`, `review`, `tests` and `verifier_passed` into it, and
  `states.verifier_passed` is a **merge gate**. The state a state machine holds
  is the one part of it the schema says nothing about.

`findings` and `errors` are likewise bare arrays, while `severity == "blocking"`
is read as a release-gate input.

## Decision

**1 · One declaration per contract. `acs-messages.xsd` is the source.**
`validate_xml.py` stops carrying a parallel copy and derives its tables from the
XSD at load time. The schema is XML, `xml.etree` is already imported, and the
plugin's no-dependency rule is respected — no `lxml`, no `xmlschema`. Element
names, attribute sets, child order, text-only leaves and every enumeration
become reads of the file that already states them. The tables, and the "keep in
sync" comment, are deleted. Drift stops being a thing anyone has to prevent.

The one entry that stays hand-written is the backward-compat exemption
(`create-spec`, retired in MAR-156 and deliberately retained by MAR-164), which
is a statement about *history* — state files written by an older build — and
not about the current vocabulary. It moves to the XSD as an annotated
deprecated member so it too has one home.

**2 · Delegation keys are typed.** `constraint/@name` becomes an enumeration of
the constraint names agents actually consume. A typo then fails validation at
the coordinator, where it can be fixed, instead of silently reaching the
executor as an absent value it has a plausible behaviour for. Adding a new
constraint becomes an edit to the vocabulary — which is the point: the set of
things one agent may tell another is a contract, not a convention.

**3 · State is declared where it is load-bearing.** `states` gets its real
shape (`plan_approved`, `pr`, `review`, `tests`, `verifier_passed`, and the
per-skill members the apply skills write), `runs[].escalations` gets the
13-field shape its writer already documents, and `findings[]` gets `severity`
at minimum, since a release gate reads it.

**4 · Nothing is declared that nothing emits.** `result/@lens` is resolved one
way or the other in the same change: either the verifier's prose is wired to
emit it and it becomes the round-trip it was meant to be, or it is dropped and
`verify_lens` stays the single encoding. It does not stay declared-and-dead.

## Consequences

- `validate_xml.py` gets smaller and stops being a place where the contract can
  be wrong. Its tests change from asserting table contents to asserting that the
  derivation matches the XSD.
- Typing `constraint/@name` is a breaking change for any message using a name
  outside the vocabulary — which is the intent, and the migration is to name the
  constraint correctly.
- Declaring `states` means a skill adding a new state member must declare it.
  That is the cost, and it is the same cost that made `guard_events` legible
  while `escalations` is not.
- The state schemas are already exercised by `tests/acs/` (six modules
  reference them), so the additions land with enforcement rather than as prose.
- This ADR is about the contracts, not the machinery that emits them. It
  composes with **ADR-0092**: fewer subagents mean fewer delegation payloads,
  and a typed payload makes the ones that remain checkable.
