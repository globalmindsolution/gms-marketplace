<!--
  test-strategy — built-in quality doc-set template (used by /acs:create-quality).
  Bootstrapped verbatim into the consumer's quality_path, then lightly tailored
  to the detected tech stack. No runtime placeholders — tailoring is an
  in-place prose edit, not a string substitution.
-->
# Test strategy

## Testing philosophy

<!-- State the product's testing philosophy and the shape of its test pyramid
(unit vs integration vs end-to-end proportions and why). -->

## Coverage policy

<!-- Summarize the test_coverage_percent target and the rationale for it;
link to coverage-policy.md for the enforceable detail. -->

## Suite inventory

<!-- List the configured test suites and what each one covers. -->

## CI gates

<!-- Describe which suites and enforcement settings gate CI (tests/enforcement
from settings.json) and what blocks a merge. -->

## Flaky-test policy

<!-- Describe how flaky tests are detected, quarantined, and tracked back to a fix. -->
