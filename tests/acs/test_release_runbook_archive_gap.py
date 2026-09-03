"""MAR-306 — release runbook diagnosis + accepted-limitations guard (AC-1, AC-6).

Prose-assertion guard, mirroring `test_release_skill_registry.py`'s style:
pins that `docs/operations/release-runbook.md` carries (a) all four evidenced
causes of the merge-pr adoption gap with their citations, explicitly
classified as a process/tooling/state-locality gap rather than a deliberate
choice, and (b) the accepted limitations of the git-log enumeration fallback
plus its forward-fix owner and human-review backstop.

Run:  python3 -m unittest tests.acs.test_release_runbook_archive_gap -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNBOOK_PATH = os.path.join(REPO_ROOT, "docs", "operations", "release-runbook.md")


def _read_runbook():
    with open(RUNBOOK_PATH, encoding="utf-8") as fh:
        return fh.read()


class MergedTicketEnumerationGapDiagnosisTest(unittest.TestCase):
    """AC-1: a written diagnosis, with evidence, of why /acs:merge-pr was not
    invoked for MAR-71..MAR-305 and PR #391."""

    def setUp(self):
        self.body = _read_runbook()

    def test_runbook_documents_why_the_sanctioned_merge_path_was_not_used(self):
        # (a) all four evidenced causes, each carrying its citation.
        self.assertRegex(
            self.body,
            r"(?i)state-locality gap",
            msg="runbook must name the state-locality gap as a cause",
        )
        self.assertIn(
            "ADR-0086", self.body,
            "the state-locality cause must cite ADR-0086 (relocatable workspace root)",
        )
        self.assertIn(
            ".acs/settings.local.json", self.body,
            "the state-locality cause must cite the gitignored local override "
            "that points this host's workspace outside the repo",
        )

        self.assertRegex(
            self.body,
            r"(?i)phantom.?gate",
            msg="runbook must name the phantom-gate / tooling cause",
        )
        self.assertIn(
            "ADR-0028", self.body,
            "the phantom-gate cause must cite ADR-0028 (m6 approved-review mandate)",
        )
        self.assertIn(
            "prd.md:102-113", self.body,
            "the phantom-gate cause must cite the PRD's merge-gate-friction problem",
        )

        self.assertRegex(
            self.body,
            r"(?i)environment gap",
            msg="runbook must name the environment (gh-unavailable) cause",
        )
        self.assertRegex(
            self.body,
            r"HTTP 403|403 in this (session|environment)",
            msg="the environment cause must cite the reproducible gh 403 evidence",
        )

        self.assertRegex(
            self.body,
            r"(?i)process seam",
            msg="runbook must name the process-seam cause",
        )
        self.assertIn(
            "ship/SKILL.md", self.body,
            "the process-seam cause must cite ship/SKILL.md stopping at create-pr",
        )
        self.assertIn(
            "CLAUDE.md", self.body,
            "the process-seam cause must cite this repo's CLAUDE.md merge-pr guidance",
        )

        # (b) explicit classification: process + tooling + state-locality gap,
        # not a deliberate choice.
        self.assertRegex(
            self.body,
            r"(?i)process gap.{0,40}tooling gap.{0,40}state-locality gap"
            r"|state-locality gap.{0,80}process.{0,40}tooling",
            msg="runbook must classify the cause set together as "
                "process + tooling + state-locality gap",
        )
        self.assertRegex(
            self.body,
            r"(?i)not\s+(?:a\s+)?deliberate\s+choice",
            msg="runbook must explicitly rule out 'deliberate choice' as the "
                "classification (definition of done requires stating "
                "process/tooling gap vs. deliberate choice explicitly)",
        )


class MergedTicketEnumerationAcceptedLimitationsTest(unittest.TestCase):
    """AC-6: the accepted limitations of the fallback, its forward-fix owner,
    and the human-review backstop."""

    def setUp(self):
        self.body = _read_runbook()

    def test_runbook_states_the_accepted_limitations_and_the_forward_fix_owner(self):
        # (c) forward fix owner = PRD G26, with G19 bypass-visibility mention.
        self.assertIn(
            "G26", self.body,
            "runbook must name PRD G26 as the forward-fix owner for the "
            "adoption gap itself",
        )
        self.assertIn(
            "G19", self.body,
            "runbook must mention G19 (bypass-rate visibility) alongside G26",
        )

        # (d) accepted limitations of the git-log fallback.
        self.assertRegex(
            self.body,
            r"\[#\d+\]",
            msg="runbook must cite the tracker-ref-only squash subject shape "
                "(e.g. '[#399] ...') as an unrecoverable-offline limitation",
        )
        self.assertRegex(
            self.body,
            r"(?i)not recoverable offline|cannot be recovered offline",
            msg="runbook must state tracker-ref-only subjects are not "
                "recoverable offline",
        )
        self.assertRegex(
            self.body,
            r"(?i)shallow clone",
            msg="runbook must state that a shallow clone bounds recall",
        )
        self.assertRegex(
            self.body,
            r"(?i)no\s+`?parent`?.{0,60}(no\s+`?docs_only`?|docs_only)"
            r"|`?docs_only`?.{0,60}`?parent`?",
            msg="runbook must state git-log-derived entries carry no parent "
                "and no docs_only",
        )
        self.assertRegex(
            self.body,
            r"(?i)accepted limitation",
            msg="runbook must explicitly label these as accepted limitations, "
                "not open bugs",
        )

        # (e) human-review backstop.
        self.assertIn(
            "ADR-0052", self.body,
            "runbook must cite ADR-0052 (mandatory human release-PR merge) as "
            "the backstop against fallback under-count",
        )

        # Must not fabricate gh-derived evidence: no live PR count/number that
        # would require a working `gh` call to have produced.
        self.assertNotRegex(
            self.body,
            r"(?i)gh pr list.{0,80}(returned|shows|found)\s+\d+\s+merged",
            msg="runbook must not present a gh-derived merged-PR count as "
                "evidence — gh is 403 in this environment",
        )


if __name__ == "__main__":
    unittest.main()
