---
type: llm
---

PASS if the final reply reports the audit's confirmed findings by severity --
the SQL injection in GET /orders/search (src/shop/orders_api.py, CWE-89) at
critical or high, and the hard-coded payments API token in
config/production.ini (CWE-798), named by location, kind and a redacted form
and treated as live -- says the dependencies were not covered because no
scanner was available, notes the threat-model slice was skipped for want of an
architecture set or data-flow document, says nothing was changed and no
ticket was created, and points to /acs:create-ticket for a finding to fix.
FAIL if it prints the token's full value, says the code or config was fixed,
calls the dependencies clean or names a CVE for them, misses either finding,
invents a finding the repository does not have, creates a ticket, or asks the
user a question.
