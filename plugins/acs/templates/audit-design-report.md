<!--
  audit-design-report — built-in template for the report /acs:audit-design writes to
  steps/audit-design/iter-1/report.md (ADR-0122, ADR-0123). A repo's
  .acs/templates/audit-design-report.md replaces it.

  The contract, checked by the post-hook: every `## ` heading below appears in the
  report, in this order (a report may add sections of its own). Each gap is ONE
  `### ` heading under its section; an empty section says `_None._`. A section
  marked `acs:count <key>` is counted — the number of its `### ` entries is what
  states.audit.<key> records, whatever the result document claimed. HTML comments
  are authoring help, not part of the contract.
-->
# Design audit — <scope>

## Scope

<!-- The documents audited, each with its status and version from `acs.py design
check`; the code areas compared, one per gap-analyst slice. -->

## Summary

<!-- One table: kind | count. Then one sentence on what matters most. -->

## Unimplemented
<!-- acs:count unimplemented -->

<!-- Designed, not built, in an `implemented` document — a regression. One
`### <element>` per gap, then:
- **Design**: `<document>` § <heading>, status <status> v<version>
- **Code**: `path:line`, or "absent" with the search that found nothing
- **Handling**: what fixes it — the code (/acs:ship) or the design (the Design skill) -->

## Planned
<!-- acs:count planned -->

<!-- Designed, not built, in a `proposed` or `approved` document — the design ahead
of the code, expected. Same fields. -->

## Undocumented
<!-- acs:count undocumented -->

<!-- Built, not designed. Same fields. -->

## Drifted
<!-- acs:count drifted -->

<!-- Both, disagreeing. Same fields, plus both readings. -->

## Unversioned
<!-- acs:count unversioned -->

<!-- Documents with no or invalid version front matter: `### <document>` and the
problem `acs.py design check` reported. -->

## Unverified

<!-- What a gap analyst could not settle, and why. -->

## Tickets

<!-- The tickets created from this report, by gap group — or "none". -->
