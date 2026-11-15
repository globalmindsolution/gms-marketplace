---
type: llm
---

PASS if the final reply says the audit confirmed nothing at any severity,
mentions that a candidate (the f-string queries in src/shop/stats.py) was
refuted because only a constant table name is interpolated and the input is
bound -- or, if no candidate was raised, simply reports nothing confirmed --
says the threat-model slice was skipped because the architecture set has no
data-flow (or cross-cutting) document and points to /acs:setup or
/acs:create-architecture to add one, and says nothing was changed and no
ticket was created.
FAIL if it reports a confirmed vulnerability in this repository, presents
the stats.py queries as an injection, claims the code was checked against a
threat model, says it wrote a data-flow diagram or changed any file, creates
a ticket, or asks the user a question.
