<!--
  test-scheduling — built-in operations doc-set template (used by /acs:create-operations).
  Bootstrapped verbatim into the consumer's operations_path, then lightly tailored
  to the detected tech stack/deployment. No runtime placeholders — tailoring is an
  in-place prose edit, not a string substitution.
-->
# Test scheduling

## The /acs:test scheduling recipe

<!-- Describe how to invoke /acs:test headless on a schedule: point a Claude
Code routine, cron entry, or CI job at `claude /acs:test` and let it choose
which configured suites to run. acs does not run its own scheduler — the
caller (cron/CI/a Claude Code routine) decides when. -->

## Example cron/CI snippets

<!-- Provide example snippets showing how to schedule a headless
`claude /acs:test` invocation from cron and from this product's CI system. -->

## Where results land

<!-- Describe where the results of a scheduled /acs:test run are written
(the results artifact) and how to find the outcome of the most recent run. -->
