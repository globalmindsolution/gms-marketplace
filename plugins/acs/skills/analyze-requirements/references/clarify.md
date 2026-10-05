# /acs:analyze-requirements — the document and feature questions

Open this when `acs.py docs where --doc analysis.md` reports a non-empty
`needs`, or when the run has no feature yet: both are group-(d) questions in
Stage 2's ONE grouped ask. A run whose saved choice decides silently, and
whose ticket or requirements already name the feature, reads none of it.

**Where the cross-references below point.** "Two modes" and "Stage 2" are
SKILL.md's sections.

When `docs where` reports `needs`:

- **`share`** → two group-(d) questions in the SAME grouped ask, never a
  separate one: "share run documents in the repo, or keep them local?" and
  "save this for you (this machine: `.acs/settings.local.json`) or for the
  team (`.acs/settings.json`)?"
- **`location`** → the folder resolves only to acs's built-in default
  (`location_source: default` — no `docs.*_dir` setting, no existing folder):
  one group-(d) question — use `proposed_path`, give another repo-relative
  folder, or keep documents local (the share answer, so its scope is asked
  too; not offered for `living:prd`). acs never creates a new docs folder
  without that answer.

Record each answer in the ledger like any other, then save it with ONE call
carrying only what was answered; it prints the new `where`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" docs decide --share yes --scope team --location development=docs/development --doc analysis.md
```

When the user is not reachable (SKILL.md's Stage 2) and `needs` is non-empty, a
Development run keeps the analysis LOCAL for this run only — `acs.py docs decide --share no --scope run`,
nothing saved — and say so in the report. A Discovery run whose folder is
still open cannot publish without the answer: finish `interrupted`,
`stop_reason: "needs_input"`, with the location question in `<questions>`.

### The feature — named or inferred, in the same ask

Every analysis is filed under a PRD feature (Two modes, above). A ticket run
takes its ticket's first `features` slug; a run whose requirements name a
feature (`context.requirements.feature`, or a PRD feature document among the
sources) takes that one. Otherwise — a ticketless prompt or an attached spec,
or a ticket with no `features` — the feature is a group-(d) question in the
SAME grouped ask, never a separate round-trip: offer the PRD feature slugs the
survey proposed, best first (each from `acs.py slug --text "<PRD feature
name>"`), and a new slug derived the same way when none fits. Record the
answer in the ledger and then with `acs.py requirements refine` as
`{"feature": "<slug>"}` (SKILL.md's "Confirmed requirements are
refined") — `acs.py analysis publish` refuses a run that
has no feature recorded, naming this step.
