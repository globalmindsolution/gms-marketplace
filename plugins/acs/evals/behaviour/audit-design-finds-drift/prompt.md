---
description: >-
  /acs:audit-design on a brownfield repo whose versioned architecture set
  (HLD plus one LLD feature document, all status implemented) has fallen
  behind the code: the HLD still names a notifier container and its POST
  /notifications call that the latest commit removed, no document shows the
  new orders API, and the customer-listing LLD says the page size defaults
  to 50 where the code says 20. It should report one gap of each kind --
  unimplemented (a regression, since the documents are implemented),
  undocumented and drifted -- each cited on both sides, and edit nothing.
expected_outcome: >-
  steps/audit-design/iter-1/gaps.md lists the notifier under Unimplemented,
  the orders API under Undocumented and the 50-vs-20 page size under Drifted;
  result.json's states.audit counts at least one of each with planned 0 and
  unversioned 0; every file under docs/architecture is byte for byte as the
  scaffold left it; no doc, code or ticket is created.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:audit-design skill on the whole architecture set in
docs/architecture/ -- the HLD and every feature's low-level design -- against
the code as it is on main now. A run for this audit is already open on this
checkout. Report every gap you find and how you classified it. Don't change
any document or any code, and don't create tickets for the gaps: when it
offers to ticket them, the answer is no. Don't ask me anything else.
