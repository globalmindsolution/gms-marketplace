# /acs:create-ticket — splitting an existing oversized ticket

Open this ONLY when `$ARGUMENTS` asks to split or restructure an existing
local ticket. This mode creates nothing new either: it converts one ticket
into an epic that keeps its id, and cuts children at the seams an oversize
analysis already found. A run that mints a fresh ticket never reads it.

The sizing rubric this mode cuts children against stays in SKILL.md, beside
Step 1, because Step 1's PR-size reading needs the same bar on every run.

**Where the cross-references below point.** Step numbers (Steps 1-4),
`Resume & reconcile` and `Finish` are SKILL.md's, and a bare "below"
means there. Step 5 is
`${CLAUDE_PLUGIN_ROOT}/skills/create-ticket/references/tracker-sync.md`.

## Splitting an existing oversized ticket

Check this BEFORE the import check: when `$ARGUMENTS` asks to split/restructure
an existing local ticket (e.g. `split SHOP-123 per <plan path>` — a
user-invoked restructure, optionally informed by `/code`'s plan-time oversize
signal, ADR 0069), this run restructures instead of creating:

- Start with `acs step start --skill create-ticket --ticket <id>` (no
  `--allocate` — the partition exists). Read the existing `ticket.json` and the
  referenced oversize analysis (the `/code` plan artifact lists the
  evidence and split seams).
- The coordinator (or executor) analyzes the split inline: the ticket becomes
  an **epic keeping its id**, description, priority, and PRD trace;
  `needs_design` becomes `true` (epics always — an existing approved design in
  the partition counts as that design); children are cut at the analysis' seams,
  each sized to ONE reviewable PR and independently shippable.

- The executor rewrites `ticket.json` (type `epic`, `children` filled) and
  mints each child with `new-ticket.py --parent <id>` — using Step 4's mint
  command block and conservative-defaults rule (below); when tracker sync is on,
  update the remote issue's type/links accordingly.
- If downstream work already exists (specs, a branch), say so and get the
  user's confirmation first; prior state files stay in the epic's partition as
  history — children start their own pipelines fresh.
