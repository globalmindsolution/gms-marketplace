# 0005 — XML subagent messaging validated by XSD

**Status**: Accepted — amended by [0100](0100-message-contract-checked-in-one-language.md) (the XML wire format and the file-reference rule stand; the XSD and `validate_xml.py` are gone) · **Date**: 2026-06-12

## Context

Coordinator ↔ subagent traffic must be machine-checkable; malformed messages
should fail fast, not silently degrade the pipeline.

## Decision

Three message shapes (`task`, `result`, `handoff`) defined in
`acs-messages.xsd`; every message validated on send and receive
(`validate_xml.py`: xmllint when present, stdlib structural fallback —
hooks stay stdlib-only). Results carry file references, never artifact
bodies; a subagent's final message is the `<result>` element alone.

## Consequences

One re-request then hard failure on invalid messages; compact handoffs keep
/ship's context clearable; the XSD is the normative schema even where only
the structural fallback runs.

## Implementation note (MAR-61)

As of MAR-61, the engine default was inverted: the in-process stdlib structural
validator (`validate_structurally` in `validate_xml.py`) is now the **default
fast path** for every message.  `xmllint` is now **opt-in** via the
`ACS_XML_AUTHORITATIVE=1` environment variable (PATH-guarded; absent xmllint
never blocks a verdict).  The in-process validator matches xmllint for the
following covered violation classes: bad root element, missing/invalid attribute,
bad ticket-id pattern, out-of-order children, wrong list-item tag, bad
status/severity enum, duplicate maxOccurs=1 sequence children (cardinality), and
xs:decimal grammar for cost-usd (no exponent, no inf/nan, no underscores).  The
AC-2 parity corpus (`tests/acs/test_acs_plugin.py:TestValidators`) is the
binding proof for these classes.  Classes not explicitly listed are not guaranteed
to match.  The Decision and Consequences sections above remain unchanged — the XSD
is still the normative authority; only the runtime engine changed.

## Amendment — v0.5.0 (the implementation-pipeline redesign)

`acs-messages.xsd` and `validate_xml.py` were both removed in v0.5.0
(`REDESIGN-IMPLEMENTATION-PIPELINE.md` §6), which retires the Consequences'
"the XSD is the normative schema even where only the structural fallback runs".
There is no XSD; the structural check **is** the contract now, not a fallback
to one. The MAR-61 note above, which had already made the in-process validator
the default engine, was the first half of that move.

The rest of the Decision stands and is still what runs. A subagent's final
message is still a `<result>` (or `<handoff>`) element and nothing else; it is
still validated on receive, with one re-request then hard failure; and results
still carry **file references, never artifact bodies** — which is the clause
that makes the small contract sufficient, because the body is a path and the
file at that path is what a schema validates.

What replaced the XSD is recorded in
[0100](0100-message-contract-checked-in-one-language.md): the message contract
is the attributes the snapshot path is derived from, checked in
`acs_lib.lifecycle.validate_message`, and the documents a step writes are JSON
validated by JSON Schema.
