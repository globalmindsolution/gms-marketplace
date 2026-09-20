# 0100 — The message contract is checked in one language; the XSD is retired and documents are JSON

**Status**: Accepted · **Date**: 2026-09-20

**Amends**: [0005](0005-xml-messaging-with-xsd.md) (the wire format and the
file-reference rule stand; "the XSD is the normative schema" does not),
[0093](0093-one-declaration-per-contract.md) (part 1's source file is gone;
its principle is applied harder elsewhere)

## Context

ADR-0005 decided that coordinator ↔ subagent traffic is XML, validated on send
and receive against `acs-messages.xsd` by `validate_xml.py`. ADR-0093 part 1
then made the XSD the single source and derived the validator's tables from it
at load time, so drift between the two stopped being something anyone had to
prevent.

v0.5.0 removed both files (`REDESIGN-IMPLEMENTATION-PIPELINE.md` §6). The
removal line reads "XML messaging: `validate_xml.py`, `acs-messages.xsd`,
`*-task.xml` snapshots → phase results are JSON, validated in the hook", and
that is half true in a way worth recording, because the half that is not true
is the half a reader would act on.

**The wire format did not go away.** A subagent's final message is text, and
the shape acs asks for is still a `<result>` or `<handoff>` element — that is
what Claude Code hands back, and `write_phase_snapshot` still persists it
verbatim (which is why `phase_artifact_path` names the file `.xml`: calling it
`.json` did not make its bytes JSON, it only made every JSON reader downstream
fail on it). What went away is the *schema in a second language*.

So after v0.5.0 the contract that actually runs was stated in one docstring
(`acs_lib.lifecycle.validate_message`) and in no ADR. Two ADRs pointed at a
file that no longer exists, and nothing recorded what replaced it. This ADR
records it.

## Decision

**1 · Two contracts, not one, and they are different kinds of thing.**

| | carries | shape | checked by |
|---|---|---|---|
| **message** | a subagent's return to its coordinator | XML element | `acs_lib.lifecycle.validate_message`, at `SubagentStop` |
| **document** | what a step writes to disk | JSON | JSON Schema, in the hooks |

Conflating them is what put an XSD in the repository: the message was made to
carry the document's weight, so the message needed the document's rigour.

**2 · The message contract is the small set of facts the kernel derives a path
from, checked in Python.** Well-formed; root in `RESULT_ROOTS`
(`result`, `handoff`); a non-empty `skill`. For a `<result>`, additionally a
non-empty `phase` and — when present — an `iteration` that is a positive
integer. A `<handoff>` has neither: it is a step coordinator's return to
`/acs:ship`, not a phase's output, and there is no snapshot path to derive from
it, so requiring them would refuse every correct handoff. An invalid message
sends the subagent back with the errors, at most `BLOCK_LIMIT` (2) times.

That is the whole contract, and it is deliberately small: it is the set of
attributes `write_phase_snapshot` needs in order to file the message, not an
attempt to describe the message's meaning. Meaning lives in the document.

**3 · The document contract is JSON Schema, declared once per contract.**
`result.schema.json` (what a step writes when it ends, and the post-hook's
input), `verdict.schema.json`, `run.schema.json`, `step-state.schema.json`, and
— for the `states` keys and `outcome` vocabulary a skill owns — a fragment
beside the skill at `skills/<name>/state.schema.json`. The envelope is
validated centrally; the per-skill part is validated against the skill's own
fragment, which is what makes adding a skill a directory rather than an edit to
a central schema.

**4 · A result still carries file references, never artifact bodies.** This is
ADR-0005's rule, kept verbatim and now load-bearing for a second reason: the
message body being a path is exactly why the message needs no schema. The file
at that path is the thing a schema validates.

**5 · No second language, and no third.** The no-dependency rule is unchanged:
no `lxml`, no `xmlschema`, no `jsonschema`. Where the evals validate schemas
they use `runner/jsonschema_mini.py`, a stdlib subset validator that raises on
any keyword it does not implement rather than silently passing — a schema that
grows one fails loudly.

## Consequences

**ADR-0005 survives in halves.** "Three message shapes", "validated on send and
receive", "one re-request then hard failure", and "results carry file
references, never artifact bodies" all stand. "`acs-messages.xsd` is the
normative schema even where only the structural fallback runs" does not — there
is no XSD, and the structural check *is* the contract rather than a fallback to
one. The MAR-61 implementation note, which had already inverted the engine
default to the in-process validator, turns out to have been the first half of
this move.

**ADR-0093's principle survives and is applied harder; part 1's mechanism does
not.** "One declaration per contract" is now per *skill*, in
`skills/<name>/state.schema.json` and `skills/<name>/acs.yaml`, which is a
stronger reading of the same decision than deriving one validator from one
schema. Part 1 named a file, and the file is gone.

**ADR-0093 part 2 is not carried over, and that is a regression this ADR
records rather than blesses.** `constraint/@name` was typed so a typo failed at
the coordinator instead of reaching the executor as an absent value it had a
plausible behaviour for. A coordinator still writes
`<constraint name="docs_only">`, and nothing enumerates the names any more.
The failure part 2 prevented is possible again. Recording it is the point: the
cost was accepted to remove a second schema language, not overlooked, and the
fix — declaring a skill's accepted constraint names in its own `acs.yaml`,
where its reads and writes already are — is the shape the rest of this decision
points at.

**ADR-0093 part 4 resolved the "wire it up" way.** `lens` is not
declared-and-dead: it is an enumerated field (`A`–`E`) on every finding, and a
nullable field on a report that says whether a single lens or the coordinator
wrote it.

**What is no longer refused.** A structurally valid message carrying an
attribute nobody declared now passes. Under the XSD it did not. That is the
accepted cost of the contract being small — and the check that used to catch it
caught it at the coordinator, which is also where the JSON document validation
now catches everything that matters.
