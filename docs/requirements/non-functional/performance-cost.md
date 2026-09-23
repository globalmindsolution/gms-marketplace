# Performance & cost

Quality requirements bounding the pipeline's token/time footprint. This is a
cross-reference file, not a duplicate, per the functional/non-functional
tie-break rule.

- **acs measures no footprint.** It records no token count, no dollar figure
  and no per-run, per-ticket or per-repo totals, and ships no dashboard for
  them ([ADR 0104](../../adr/0104-no-usage-dashboards-no-usage-recording.md));
  see [../functional/workspace-and-state.md](../functional/workspace-and-state.md#no-usage-recording).
  Tokens, spend and time per ticket are read where Claude Code reports them:
  its own `/cost`, the console, or its usage exports.
- **What bounds the footprint is structural**, and lives in the functional
  files: a step that owes nothing completes as an evidenced no-op at no
  token cost, and the `review-code` → `code` loop is bounded by the
  workflow's single `loops[].max_iterations`
  ([../functional/workflow.md](../functional/workflow.md)).
