<!--
  audit-security-report — built-in template for the report /acs:audit-security
  writes to steps/audit-security/iter-1/report.md (ADR-0123). A repo's
  .acs/templates/audit-security-report.md replaces it.

  The contract, checked by the post-hook: every `## ` heading below appears in the
  report, in this order (a report may add sections of its own). Each finding is ONE
  `### ` heading under its section; an empty section says `_None._`. A section
  marked `acs:count <key>` is counted — the number of its `### ` entries is what
  states.audit.<key> records, whatever the result document claimed. HTML comments
  are authoring help, not part of the contract.
-->
# Security audit — <scope>

## Scope and coverage

<!-- The paths audited; the slices run and skipped, each skip with its reason; the
scanners each dependency auditor ran and the ecosystems with none. A category with no
coverage is "uncovered", never "clean". -->

## Summary

<!-- One table: severity | confirmed. Then one sentence on the worst finding. -->

## Critical
<!-- acs:count critical -->

<!-- One `### <id> · <title>` per confirmed finding, then:
- **CWE**: CWE-<n> (<OWASP category>)
- **Location**: `path:line`
- **Evidence**: the quoted lines, the input's path from source to sink, or the scanner output
- **Exploit scenario**: two or three sentences
- **Fix**: the guidance
- **Resolved when**: the adjudicator's resolved_when
A secret is named by location, kind and a redacted form — never its value. -->

## High
<!-- acs:count high -->

## Medium
<!-- acs:count medium -->

## Low
<!-- acs:count low -->

## Advisory
<!-- acs:count advisory -->

<!-- The needs-context findings: `### <id> · <title>`, the claim, and what the
adjudicator could not read. -->

## Refuted
<!-- acs:count refuted -->

<!-- `### <id> · <title>` and the one-line reason; the full ruling is in
iter-1/adjudication-<id>.json. -->
