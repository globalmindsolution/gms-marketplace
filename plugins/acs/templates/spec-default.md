<!--
  spec-default — built-in spec template (the default create-spec writes to each
  <partition>/specs/NN-<slug>.md). The `## ` headings below — and only the
  headings — are the enforcement contract: enforcement.spec_sections defaults to
  exactly this list, in this order, and the create-spec structure gate checks
  their presence and order. Fill each section from workspace state; the
  HTML-comment guidance is authoring help, not part of the gate.
-->
## Scope

<!-- What this spec delivers; the acceptance criteria it covers (quote them); how it depends on earlier specs, if at all. -->

## Approach

<!-- The solution shape at contract level: components and interfaces involved, algorithms, error handling, indicative paths at most. When a design exists, reference the design sections it follows; flag any deviation. -->

## API/data changes

<!-- Endpoints, contracts, schemas, migrations, config. MUST call out the documentation impact: list the consumer-repo docs this change touches (README, API/usage docs, changelog, architecture doc set). -->

## Test plan

<!-- Tests to write (TDD: /acs:code writes them first), mapped to the acceptance criteria this spec covers; state how the test_coverage_percent target applies. E2E impact: name flows + e2e tests when applicable, else "no e2e impact" with a reason. -->

## Out of scope

<!-- Adjacent work deliberately excluded (and which spec or future ticket owns it, when known). -->
