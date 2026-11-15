# /acs:manage-roadmap — the authoring notes

The surveyor writes `steps/manage-roadmap/iter-1/authoring.md`; the author
completes it after writing `roadmap.md` and carries it forward as
`iter-<n>/authoring.md` on later iterations; the reviewer and the floor
(`roadmap_check.py --plan`) judge the roadmap against it. Sections, in order:

- **`## Mode & evidence`** — `create`, `amend` or `replan`, and why: whether
  `roadmap.md` exists (path), and for `replan` the drift that calls for it (a
  feature cut, added or re-prioritised in the PRD, quoted with its line).
- **`## PRD features`** — the hub's Features index as the surveyor read it, one
  line per feature: `- <slug> — <Must|Should|Could|Won't> — supports G1, G3`,
  each with the `prd.md` line it rests on. A feature PRD that does not exist is
  recorded as such, never invented.
- **`## Delivery evidence`** — the output of `acs.py roadmap status` (never
  `--write` — the surveyor is read-only), quoted: each milestone's derived status
  and the tickets behind it; the epics the tickets index holds that link one of
  the PRD's features. No roadmap yet: `none — create mode`.
- **`## Roadmap outline`** — the plan: every milestone with its name, version,
  features (slugs), epics (ids, or `none yet`), target (only one the user gave)
  and its one-paragraph why. In amend/replan mode, mark each milestone `kept`
  (byte-for-byte), `changed` (what and why) or `new`, and list each one cut.
- **`## Roadmap milestones`** — the floor's grammar: one line per milestone of
  the outline, quoting its heading text without the `###`:

  ```
  - Milestone: "M1 Booking MVP — v0.1.0"
  ```

- **`## Answer fidelity`** — one line per `answered`/`assumed` entry of
  `clarifications.json`: `- C-<n> — roadmap.md — "<verbatim anchor>"`, or
  `- C-<n> N/A: <why this answer produces no anchor>`. The surveyor names the
  answers the ledger already holds; the author adds the rest and completes every
  anchor against the text it wrote. Every ledger id appears exactly once.
- **`## Open questions`** — what only the user can settle: the order of
  milestones, which feature ships first, a version, a target date. Never a fact
  the PRD, the tickets or the code already answer.
- **`## Deviations`** — the author's: each change to the outline, with the
  answer (`C-<n>`) or finding that drove it. From iteration 2, **`## Findings
  addressed`** maps each reviewer finding to the change that fixed it.

**What the floor checks** (`roadmap_check.py`, rules in its docstring): the
roadmap's own shape against `roadmap-shape.md` and the hub's index (every rule,
every mode); with `--plan`, the notes' `## Roadmap milestones` against the
document's milestone headings (both directions in create mode; in amend and
replan mode the reverse direction only for the `--added-heading` values), and the
`## Answer fidelity` anchors against the ledger.
