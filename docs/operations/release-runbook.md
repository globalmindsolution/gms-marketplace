# Release runbook

The actionable checklist for cutting a release. The *why* and the consumer-facing
mechanics live in the [root README](../../README.md#releasing--updating); this is
the step-by-step the maintainer follows.

## Preconditions

- `main` is green (tests 3.9 + 3.12, pre-commit, gitleaks, per-entry name/version consistency).
- Working tree clean; you're on a release branch off the latest `main`.

## Steps

1. **Run the pre-release quality gate** — the paid eval suite (real `claude`
   sessions; a few dollars):
   ```bash
   python3 evals/run_evals.py --paid
   ```
   Treat a clean run as the gate. Investigate any failing scenario before
   continuing — do not tag on red. (The free smoke already ran on every commit
   via pre-commit; this adds the agentic G1–G4 + cleanup coverage.)
2. **Bump the version** — set the same `version` in both
   `.claude-plugin/marketplace.json` and
   `plugins/acs/.claude-plugin/plugin.json` (by convention both are kept in
   sync), and point the acs `git-subdir` `source.ref` at the new tag.
3. **Update the changelog** — add the matching section to
   [`plugins/acs/CHANGELOG.md`](../../plugins/acs/CHANGELOG.md) (Keep a Changelog
   format); this becomes the release notes.
4. **Open the release PR**, get CI green, and merge (squash). On merge the
   Release workflow cuts the immutable `v<version>` tag and publishes the
   release from the changelog section.
5. **Verify the tag** resolves and the plugin installs from it:
   ```bash
   claude plugin marketplace add globalmindsolution/gms-marketplace@v<version>
   claude plugin install acs@gms-marketplace
   ```

## Merged-ticket enumeration — why the coverage report can under-report

Discovered cutting v0.4.8: `release_notes.py draft`'s merged-ticket coverage
report (`{"merged": 0, "covered": 0, "missing": 0}`) can read as empty even
when real merged tickets exist, because its enumeration reads exclusively
from `archive/<ticket-id>/`, and that directory is written by exactly one
place — `/acs:merge-pr`'s cleanup step (`_archive_partition()`, reached only
from `run_post_skill()`'s `skill == "merge-pr" and status == "completed"`
branch). A ticket merged any other way never gets an archive entry, so it is
invisible to the archive-only path. `enumerate_merged_tickets()` now also
recovers such tickets from `base_branch` commit-subject history (see
`plugins/acs/skills/release/SKILL.md`); this section records why the gap
exists and what the fallback does and does not fix.

### Why `/acs:merge-pr` was not invoked for MAR-71..MAR-305 and PR #391

Four causes, each independently evidenced — together they explain the gap
without any single cause being sufficient on its own:

1. **State-locality gap (dominant).** `archive/` lives inside the acs
   pipeline workspace, which by default is now anchored in-repo
   (ADR-0086), but this host's `.acs/settings.local.json` (gitignored)
   overrides it to an external, machine-local path
   (`workspace_path: /home/user/acs-workspace`, directory created
   2026-09-01). That workspace holds exactly one ticket (`MAR-306`) and no
   `archive/` directory at all — so even a history of perfectly-executed
   `/acs:merge-pr` runs elsewhere would still read as zero merged tickets on
   this host. State that is machine-local by design (or by override) cannot
   be assumed present on the machine cutting the release.
2. **Phantom-gate (tooling gap).** ADR-0028's mitigation **m6** requires an
   APPROVED review on every `/acs:merge-pr` invocation, implemented as the
   conservative require-APPROVED-for-all fallback. On a solo-author repo
   whose own branch protection requires zero reviews, GitHub forbids
   self-approval, so a solo author can never satisfy m6 and therefore cannot
   use `/acs:merge-pr` at all — already documented as the **acs
   merge-gate-friction problem** in `docs/product/prd.md:102-113` ("the
   observed consequence is PRs merged out-of-band directly on GitHub … each
   such merge strands the ticket at `in_review` (never archived …)").
3. **Environment gap.** `/acs:merge-pr` is entirely `gh`-driven; in this
   session both `gh api repos/.../pulls` and `gh pr list --json ...` return
   HTTP 403 ("GitHub access is not enabled for this session" /
   "This GraphQL query is not enabled for this session"), so the skill
   cannot run here at all regardless of the review-gate question above.
4. **Process seam.** `/acs:ship` deliberately stops at `create-pr` and
   never runs `/acs:merge-pr` itself (`plugins/acs/skills/ship/SKILL.md:30`,
   `:89`); this repo's own `CLAUDE.md` names `/acs:merge-pr` only in its
   `--pr` exempt-PR form (`CLAUDE.md:23,28`). Nothing in the default
   pipeline path routes a ticket PR to the sanctioned merge step, so a human
   merging the PR on GitHub — the only remaining option once causes 2 and 3
   apply — is the path of least resistance, not an explicit choice to skip
   the tooling.

**Classification:** this is a **process gap + tooling gap + state-locality gap**,
**not a deliberate choice** to bypass `/acs:merge-pr`. Every observed
out-of-band merge is downstream of the three technical obstacles above
(phantom self-approval gate, `gh` unavailability, no default routing to the
merge step) compounded by archive state that is not guaranteed to be present
on the host generating the release. No evidence anywhere in the ticket
history, the PRD, or the ADR set suggests `/acs:merge-pr` was available and
skipped on purpose.

### Forward fix

Closing the adoption gap itself — making `/acs:merge-pr` usable for a
solo author and reconciling tickets stranded by out-of-band merges — is
**PRD G26** ("Invoker-scoped merge governance + out-of-band reconciliation",
`docs/product/prd.md:192`), which narrows m6's require-APPROVED-for-all
fallback once a reliable invocation-source signal exists. Visibility into how
often merges bypass the sanctioned path is folded into **G19**
("Failure-mode / pipeline-health observability", `docs/product/prd.md:185`)
by extension. This ticket (MAR-306) does not implement G26 or G19; it only
makes the release-cut coverage report robust to the gap G26 will eventually
close.

### Accepted limitations of the git-log fallback

The `base_branch` commit-history fallback is a defensive recovery signal
(already the sanctioned shape for PR-ref resolution per
`docs/adr/0051-changelog-archive-primary-coverage-check.md:33-36`), not a
complete substitute for the archive. Its limitations are **accepted**, not
open bugs to fix under this ticket:

- **Tracker-ref-only squash subjects are not recoverable offline.** A
  subject like `[#399] Fix panel-6 ... (#413)` carries the tracker issue
  number the GitHub UI assigned, not the acs ticket id
  (`docs/adr/0035-pr-title-ticket-ref-token.md`), and the acs id appears
  nowhere else in the commit (verified: `git log -1 --format=%B` on that
  commit shows no `MAR-N` token anywhere in subject or body). Such tickets
  under-count regardless of the fallback.
- **A shallow clone bounds recall to whatever history was actually
  fetched.** This checkout is shallow (`git rev-parse
  --is-shallow-repository` → `true`, 49 commits on `main`); a CI checkout
  configured with a shallower `fetch-depth` would recover fewer tickets
  still.
- **Git-log-derived entries carry no `parent` and no `docs_only`.** Unlike
  an archived ticket's partition, a commit subject alone cannot recover
  epic grouping or the docs-only flag, so such entries render as flat
  bullets categorized from the title alone.
- The `--ticket-prefix` flag (`draft`/`bump`, passed by `/acs:release` as
  the configured ticket prefix) narrows the match to this repo's own prefix
  and reduces false positives from unrelated `XXX-123`-shaped tokens, but it
  does not change which subjects carry a recoverable ticket id in the first
  place — it cannot make a tracker-ref-only subject match.

The resulting count is **non-zero and honest about its source** (each
enumerated ticket is stamped `"source": "archive"` or `"source": "git-log"`)
but **not guaranteed complete**.

### Human-review backstop

The under-count above is bounded by the mandatory human checkpoint already
in the release-cut design: ADR-0052 requires every release to land via an
exempt `release/*` PR that stops for a human to review and merge — the skill
never tags or publishes on its own. A human reviewing the generated
changelog section before merge is the backstop against the fallback missing
a ticket, independent of anything `release_notes.py` computes.

## Rollback

A release is just a tag. To roll back, **re-pin** consumers to the previous
`v<version>` tag (managed settings `ref`, or `@v<version>` on add) and reload;
then cut a fix-forward release. Never delete a published tag — pinned consumers
depend on its immutability.

## See also

- [root README — Releasing & updating](../../README.md#releasing--updating)
- [quality/testing-strategy.md](../quality/testing-strategy.md) — why the paid
  evals are the gate
- [m2-0-validation-spike.md](../product/m2-0-validation-spike.md) — the
  end-to-end install/run validation runbook
