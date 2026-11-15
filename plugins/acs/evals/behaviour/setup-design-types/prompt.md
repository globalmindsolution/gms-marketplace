---
description: >-
  /acs:setup asked to change which design documents the Design skills write:
  add the data-flow (threat model) diagram to the HLD and drop the physical
  schema from the LLD, everything else default. setup must offer the
  catalog `setup detect` reports and write exactly that choice through
  `setup apply` as `design.hld_types` / `design.lld_types`, and install no
  CI gate (ADR-0120).
expected_outcome: >-
  .acs/settings.json carries design.hld_types = the default HLD types plus
  data-flow, and design.lld_types = the default LLD types without
  physical-schema; no CI gate installed; the reply names the two changes.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:setup skill. Our architects want the data-flow diagram with trust
boundaries in the high-level design, for threat modelling. We use a schemaless
document store, so drop the physical schema from the low-level design. Keep
every other design document at its default, keep the ticket prefix, and don't
add any CI check. Don't ask me anything.
