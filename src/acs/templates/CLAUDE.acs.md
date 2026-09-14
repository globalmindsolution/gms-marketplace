<!--
  CLAUDE.acs.md — acs managed block, written/refreshed by /acs:setup into the
  consumer repo's own CLAUDE.md. Everything between the BEGIN and END markers is
  owned by acs and replaced wholesale on each re-run; edit guidance here, not in
  the consumer CLAUDE.md. Placeholders: {ticket_prefix}, {exempt_label}.
-->
<!-- BEGIN acs-managed (do not edit inside this block) -->
## Working in this repo with acs

This repository uses **acs** (the agentic coding system). The pipeline is the
default path for changes — do not hand-roll branches, commits, or PRs that
bypass it.

- **When asked to implement or code a ticket, use `/acs:ship <ticket-id>`** (or
  a single step such as `/acs:code <ticket-id>` when you want just that step).
  Let the skill open the PR via
  `/acs:create-pr` — never open it yourself with `gh pr create`. The pipeline
  reads **this project's** naming rules from `.acs/settings.json`
  (`formats.branch_name`, `formats.pr_title`, `formats.commit_message`, required
  PR sections, the `ACS` label) and renders the branch, title, body, and label
  to match. The CI convention gate validates against the same settings, so a
  pipeline-produced PR passes by construction; a hand-made PR bypasses the
  rendering and fails the gate.
- **`/acs:ship` takes a ticket id, not a prompt.** A brand-new change starts at
  `/acs:create-ticket "<request>"` (and `/acs:create-design <ticket-id>` when the
  ticket needs a design); then `/acs:ship <ticket-id>` drives the delivery
  pipeline to the PR. The steps and their order are declared in the plugin's
  `workflows/ship.yaml` (a repo may override it at
  `.acs/workflows/ship.yaml`) — read that file rather than assuming an order;
  `acs.py workflow next --ticket <ticket-id>` prints what runs next. Ship always
  stops before merge.
- **Ticketed work uses the `{ticket_prefix}-N` prefix.** Reference the ticket id
  in branch names and commits so the gate and tracker can trace the change.
- **For a legitimate one-off NON-ticket PR** (a hotfix, a chore, a doc tweak
  that does not warrant a ticket), label it with the **`{exempt_label}`** label
  and merge it via **`/acs:merge-pr --pr <PRNUMBER>`** — the sanctioned exempt
  merge path. Do **not** use a raw `gh pr merge`: it fights the
  convention-enforcement gate, which requires either a ticket-backed PR or the
  `{exempt_label}` label.

When in doubt, prefer `/acs:create-ticket` then `/acs:ship <ticket-id>`; reach
for `/acs:merge-pr --pr` only for the rare exempt PR you have already labelled
`{exempt_label}`.
<!-- END acs-managed -->
