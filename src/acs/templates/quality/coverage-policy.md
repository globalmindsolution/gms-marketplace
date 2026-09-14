<!--
  coverage-policy — built-in quality doc-set template (used by /acs:create-quality).
  Bootstrapped verbatim into the consumer's quality_path, then lightly tailored
  to the detected tech stack. No runtime placeholders — tailoring is an
  in-place prose edit, not a string substitution.
-->
# Coverage policy

## Target and hard-fail rule

<!-- State the test_coverage_percent target and whether missing it hard-fails
the pipeline or is a soft warning. -->

## Exclusions

<!-- List what code is out of scope for the coverage measurement (generated
code, vendored dependencies, migrations, etc.) and why. -->

## Measurement per stack

<!-- Describe how coverage is measured per stack/language (tool, command,
report format). -->

## Escalation

<!-- Describe what happens when a PR misses the target: who is notified, what
remediation is required before merge. -->
