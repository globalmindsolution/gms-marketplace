---
type: llm
---

PASS if the final reply reports the audit's gaps by kind -- the notifier
container (or its POST /notifications call) as unimplemented and flagged as a
regression because its documents are marked implemented, the orders API as
undocumented, and the customer page size as drifted with both readings (50 in
the LLD, 20 in the code) -- cites a document and a code location for them,
says no document or code was changed and no ticket was created, and points to
/acs:create-architecture (or the LLD skill) for the design fixes.
FAIL if it reports editing, regenerating or re-versioning any document,
calls the notifier "planned", misclassifies any of the three gaps, invents a
gap the repository does not have, creates a ticket, or asks the user a
question the request already answered.
