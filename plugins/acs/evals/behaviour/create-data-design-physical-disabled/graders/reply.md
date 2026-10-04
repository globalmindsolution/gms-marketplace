---
type: llm
---

PASS if the final reply reports the orders feature's logical ERD written
under docs/architecture/lld/orders/data/ for EVAL-1, and says no physical
schema was written because `physical-schema` is not enabled in the repo's
design.lld_types (or equivalent wording about the setting), with no
migration or code written.
FAIL if it reports writing a physical schema, tables with column types, a
migration outline or a migration, claims the physical schema was skipped for
any reason other than the setting, or asks the user a question the request
already answered.
