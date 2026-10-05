# /acs:analyze-requirements — the synthesis pass and the contexts

Open this when the `synthesize` action is due — the coordinator, before it
spawns the ONE synthesis analyst — and when your task names
`<constraint name="pass">synthesis</constraint>` — the analyst, before it
starts. It says what the synthesis reconciles, how the analysis is split
into contexts, and what the synthesis writes.

## What the synthesis reconciles

The synthesis analyst reads every section across the
`<!-- slice: <id> -->` markers and, where two lanes' notes contradict each
other (a symbol one lane calls unused and another finds called, an
API-surface or design verdict the areas disagree on, one file claimed by two
seams, a criterion the requirements lane calls testable that an impact lane
shows the code contradicts), records the resolution with the evidence under a
`## Synthesis` section of the notes — or, when no source settles it, turns it
into a group-(a) question; it never silently picks one. It also de-duplicates
the lanes' `## Questions for the user` into ONE list, in the four groups, and
settles the analysis's contexts under `## Contexts` (Contexts, below). It
writes ONLY `iter-1/authoring-synthesis.md` and `iter-1/analyst-synthesis.json`,
and `record-synthesis` joins it last. In the joined `## Questions for the
user`, the `<!-- slice: synthesis -->` block is the de-duplicated list Stage 2
asks; the per-lane blocks above it stay as provenance. The impact reviewer
judges the synthesis (dimension 7), and the draft pass consumes these
reconciled notes — it does not reconcile slices itself.

### Contexts — how the analysis is split

A **context** is a bounded context the requirements touch: a part of the
product with its own rules and words — `order-checkout`, `payment-refunds` —
not a directory and not a layer. Contexts come from the impact lanes' code
areas and the PRD features together: the synthesis groups every impact row
under one context, names each in plain words with a kebab-case file name
(`acs.py slug --text "<name>"`) and a one-line purpose, and merges two
candidates that share their rules. Even a one-context analysis is a folder: a
README plus that one file. Each row, rule and risk lives in exactly ONE
context file; another file that needs it links to it instead of repeating it.

## The analyst's synthesis pass

After every survey lane returned you are spawned with `slice="synthesis"` and
the joined `iter-1/authoring.md` in `<inputs>`. The joined notes are a join,
not a synthesis — synthesizing them is your job, and it happens BEFORE the
user is asked anything. Do not re-survey the areas; open the cited files you
need to settle a contradiction.

- Read every section across its `<!-- slice: <id> -->` markers and find
  where two slices contradict each other: a fact one lane states and another
  denies, API-surface evidence from two areas that points different ways, one
  path claimed by two areas' seams with different changes, a criterion your
  requirements lane calls testable that an impact lane shows the code
  contradicts.
- Write a `## Synthesis` section to `iter-1/authoring-synthesis.md` with one
  entry per contradiction: the slices involved, what each claimed (cited), and
  either the resolution with the evidence you opened that settles it, or a
  group-(a) question in your `## Questions for the user` when no source does.
  Never silently pick one slice's claim; with no contradictions, the section
  says `_No contradictions between slices._` and names the seams you checked.
- Write a `## Contexts` section to the same file: the bounded contexts the
  analysis splits into, settled from the impact lanes' context names and your
  requirements lane's candidates — one line each: the name in plain words,
  the kebab-case file name (`acs.py slug --text "<name>"`), a one-line
  purpose, and the impact rows it owns. Merge two candidates that share their
  rules; split one whose rows answer to different rules. Every impact row
  belongs to exactly ONE context; even a single context is one entry. On a
  re-analysis keep the previous analysis's file names unless a context
  changed.
- Write a `## Questions for the user` section to the same file: the slices'
  lists de-duplicated into ONE list, in the four groups, each item naming the
  slice question(s) it stands for, plus any question your synthesis raised.
- Write your report to `iter-1/analyst-synthesis.json` (`analysis_path`
  null). Never write the merged `iter-1/authoring.md` — the controller joins
  your file into it last.
- Your result carries the slice:
  `<result skill="analyze-requirements" phase="analyst" slice="synthesis" …>`.
