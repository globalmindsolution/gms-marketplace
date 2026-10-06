# /acs:create-prd — the documents' version front matter

Open this before the first author spawn and again after every author result.
Review, whose floor re-checks both blocks, is SKILL.md's section.

1. **Before the first author spawn** (iteration 1), record where the run
   started — skip this when the file already exists (a resume):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" design check <the existing of "<prd>" "<roadmap>"> \
     > <partition>/steps/create-prd/versions-before.json
   ```

   With neither file on disk (greenfield) write `{"ok": true, "files": []}`
   there instead.
2. **After every author result**, before the review, for each of `<prd>` and
   `<roadmap>`:
   - **new, or without a block** (absent from `versions-before.json`, or listed
     there with the `no version front matter` problem):

     ```bash
     python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/acs.py" design init --status proposed "<file>"
     ```

     `init` leaves a file that already has a block alone, so a later
     iteration's call is a no-op.
   - **changed** (it had a valid block, `git diff --quiet -- "<file>"` exits 1,
     and `design check` still shows the version `versions-before.json`
     recorded): `acs.py design bump "<file>"` — version + 1,
     re-opened as `proposed`. A file already bumped in this run shows a higher
     version and is not bumped again: one run is one version.
   - **unchanged**: nothing; its block stays as it was.

   The run is ticketless, so no ticket is passed and `tickets` gains no
   entry. `bump` refuses a `deprecated` document: STOP,
   fail the run with that error and tell the user a deprecated PRD is not
   amended — nothing re-opens it.
3. `acs.py design check "<prd>" "<roadmap>"` runs again in the floor (Review),
   so a block the author broke is a blocking finding, never a silent pass.
