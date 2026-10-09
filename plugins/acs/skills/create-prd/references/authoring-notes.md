# /acs:create-prd — the authoring notes' three corroboration sections

The surveyor writes these sections (and `## Feature set`, below) into the
authoring notes, the author completes them, and the review's deterministic floor
(`prd_conformance_check.py`) parses their one-line grammars, which the
reviewer's semantic ceiling then judges. Never invent or omit them.

- **`## Code evidence`** — brownfield/amend only; N/A in greenfield. One
  line per citation, the existing house grammar, unchanged:

  ```
  - <claim text> — `<relative-path>[:<line>|:<line-start>-<line-end>]` — "<verbatim excerpt>"
  ```

  Path is backtick-quoted, relative to the repo root (never absolute, never
  `..`-escaping); line/range is advisory only; excerpt is a straight-double-quoted
  verbatim substring of the cited file. In greenfield mode the notes state `Code
  evidence: N/A — greenfield, no code to cite` instead of the section body.
- **`## Answer fidelity`** — one line per `answered`/`assumed`
  `clarifications.json` entry:

  ```
  - C-<n> — <prd.md|roadmap.md> — "<verbatim anchor text>"
  ```

  (A feature PRD is a target too: `features/<slug>/prd.md` in place of the file name.)

  or, for an answer that yields no verbatim text:

  ```
  - C-<n> N/A: <why this answer produces no anchor>
  ```

  The anchor is a straight-double-quoted verbatim substring of the named
  produced file (whitespace-normalized). Every ledger id must appear
  exactly once; an id absent from this section is
  `answer-not-dispositioned`. The surveyor writes the section with a line for every
  entry the ledger already records and names the file each answer will land
  in; the anchors point into text that does not exist yet, so the author
  completes each line's verbatim anchor — and adds the lines for the answers
  the survey's open questions produce — once it has written the documents.
  The `hub` author completes the lines that land in `prd.md` or `roadmap.md`;
  the line of an answer that lands in a feature PRD is that feature author's,
  written in its `features/<slug>/notes.md` under the same `## Answer
  fidelity` heading and grammar, and it wins over the plan's placeholder line
  for the same id (`author-slices.md`).
- **`## Feature set`** — the surveyor's draft, the `hub` author's final word, of
  the features the PRD defines: one line per feature, the cut the feature
  authors are spawned from (not parsed by the floor; the index/document check
  is `prd_feature_check.py`):

  ```
  - <slug> — "<Feature name>" — <Must|Should|Could|Won't> — supports G1, G3 — <one-line scope>
  ```

  Slugs are kebab-case and unique; the same slug names `lld/<slug>/` and a
  ticket's `features` entry, so choose the name the product already uses.
- **`## Roadmap milestones`** — one line per milestone the notes' roadmap
  outline declares, carrying the milestone's verbatim heading text as it
  will appear in `roadmap.md`:

  ```
  - Milestone: "### M2.6 — v0.3.5–v0.3.7 fast-follows — complete tracker & PR metadata sync; dynamic lane correctness"
  ```

  (This mirrors `roadmap.md:273`'s actual milestone-title shape, including
  the `;` — the grammar quotes the whole heading text so the `;` is inert,
  never a delimiter.)

**What the floor checks.** `prd_conformance_check.py` independently and
deterministically re-checks three families: the notes' `## Code evidence`
citations (family `code-evidence`; brownfield/amend only — N/A in greenfield,
never a block there), the notes' `## Answer fidelity` anchors against every
`answered`/`assumed` `clarifications.json` entry (family `answer-fidelity`;
active every mode), and the notes' `## Roadmap milestones` headings against
`roadmap.md` (family `roadmap-outline`; both directions in
greenfield/brownfield, the reverse direction scoped to the `--added-heading`
values in amend mode).
