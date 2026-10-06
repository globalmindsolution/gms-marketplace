<!--
  bug-default — built-in bug description template (used by /create-ticket).
  Placeholders: {ticket_id}, {type}, {title}, {external_key}.
-->
## Summary

<!-- One or two sentences: what is broken, for whom, and since when if known. -->

## Steps to reproduce

<!-- Numbered, minimal, from a clean state; mirrored in the ticket's `reproduction` field. -->

1. ...

## Expected behaviour

<!-- What should happen; mirrored in `expected`. -->

## Actual behaviour

<!-- What happens instead -- error text, wrong value, screenshot reference; mirrored in `actual`. -->

## Environment

<!-- Version / commit, OS, browser or runtime, configuration; mirrored in `environment`. -->

## Severity

<!-- critical | high | medium | low -- how bad the defect is, separate from priority
(how soon it is fixed); mirrored in `severity`. -->

## Suspected area

<!-- The code most likely at fault, each claim with a path:line citation; "unknown" is an answer. -->

## Acceptance criteria

<!-- These become the ticket's acceptance_criteria. The first is always the regression test. -->

- [ ] A regression test reproduces the bug — it fails before the fix and passes after it.
- [ ] ...

## References

<!-- Filled by acs, never by hand: links to this ticket's documents in the repo's standard layout (ADR-0140). Leave the two markers below as they are. -->
<!-- acs:references -->
<!-- /acs:references -->

## Notes

<!-- Workarounds, related tickets, PRD trace, open points resolved during analysis. -->

acs-ticket: {ticket_id}
