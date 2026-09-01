"""MAR-5 -- doc-set consistency for the ADR-0085 in-repo state-root rewrite.

Locks the ADR + architecture + requirements doc set's internal consistency
after the ADR-0003 -> ADR-0085 supersession (S4 of the MAR-1 epic split):
no touched file still makes the superseded "workspace lives outside the
repo" claim, ADR-0085 is cited consistently (never as the ticket's own
literal "0084" typo, and never as "(MAR-1)"/"(MAR-5)" -- MAR-1 already
denotes an unrelated, already-shipped cost-metering ticket in several of
these same files).

Stdlib-only (os, re, unittest). Run:
  python3 -m unittest tests.acs.test_state_root_doc_set -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _p(*parts):
    return os.path.join(REPO_ROOT, *parts)


ADR_0003 = _p("docs", "adr", "0003-file-based-state-outside-repo.md")
ADR_0085 = _p("docs", "adr", "0085-in-repo-anchored-state-machine.md")
ADR_README = _p("docs", "adr", "README.md")

OVERVIEW = _p("docs", "architecture", "hld", "overview.md")
DEPLOYMENT = _p("docs", "architecture", "hld", "deployment.md")
C4_CONTEXT = _p("docs", "architecture", "hld", "c4-context.md")
C4_CONTAINER = _p("docs", "architecture", "hld", "c4-container.md")
DATA_MODEL = _p("docs", "architecture", "hld", "data-model.md")
CONTRACTS = _p("docs", "architecture", "lld", "contracts.md")

WORKSPACE_AND_STATE = _p("docs", "requirements", "functional", "workspace-and-state.md")
CONFIGURATION = _p("docs", "requirements", "functional", "configuration.md")
SKILLS = _p("docs", "requirements", "functional", "skills.md")
HOOKS = _p("docs", "requirements", "functional", "hooks.md")
WORKFLOW = _p("docs", "requirements", "functional", "workflow.md")
USAGE = _p("docs", "requirements", "functional", "usage.md")
REQUIREMENTS_README = _p("docs", "requirements", "README.md")
PORTABILITY = _p("docs", "requirements", "non-functional", "portability.md")

# The 17 files this ticket's file map touches (3 ADR, 6 architecture, 8
# requirements).
TOUCHED_FILES = (
    ADR_0003, ADR_0085, ADR_README,
    OVERVIEW, DEPLOYMENT, C4_CONTEXT, C4_CONTAINER, DATA_MODEL, CONTRACTS,
    WORKSPACE_AND_STATE, CONFIGURATION, SKILLS, HOOKS, WORKFLOW, USAGE,
    REQUIREMENTS_README, PORTABILITY,
)

# Files design.md's conformance list requires to cite ADR-0085 explicitly.
CITING_REQUIRED = (
    OVERVIEW, DATA_MODEL, DEPLOYMENT, C4_CONTEXT, C4_CONTAINER, CONTRACTS,
    WORKSPACE_AND_STATE, CONFIGURATION,
)

ADR_0085_RE = re.compile(r"ADR-0085|\[0085\]|0085-in-repo-anchored-state-machine")
MAR1_TOKEN_RE = re.compile(r"\bMAR-1\b")

# Confirmed-live baseline MAR-1 citation counts (unrelated, already-shipped
# cost-metering content, ADR-0082) that this ticket's edits must not shift.
# Every touched file not listed here has a baseline of 0.
MAR1_BASELINE = {
    C4_CONTAINER: 5,
    DATA_MODEL: 27,
    CONTRACTS: 3,
    WORKSPACE_AND_STATE: 5,
    CONFIGURATION: 1,
    HOOKS: 2,
    USAGE: 1,
    PORTABILITY: 1,
}

# Stale "workspace lives outside the repo" claims each file must no longer
# carry once rewritten. Checked against whitespace-normalized text so a
# prose rewrap that moves a phrase across a line break doesn't defeat the
# check. docs/adr/0003's historical Context/Decision/Consequences body is
# deliberately excluded -- it correctly records what ADR-0003 decided at
# the time; only its Status line changes (see AdrCitationTest).
STALE_CLAIMS = {
    OVERVIEW: ("workspace folder outside that repo",),
    DEPLOYMENT: ("outside every checkout",),
    C4_CONTEXT: ("Outside the repo:",),
    WORKSPACE_AND_STATE: ("MUST live **outside the consumer repo**",),
    CONFIGURATION: (
        "MUST be **outside the consumer repo**",
        "MUST refuse a `workspace_path` that is inside the consumer repo",
    ),
    SKILLS: (
        "MUST prompt the user for `workspace_path` — there is no default",
        "outside the consumer",
    ),
    HOOKS: ("valid and outside the repo",),
    WORKFLOW: (
        "workspace_path` is machine-local)",
        "the workspace lives **outside** the consumer repo",
    ),
    USAGE: (
        "must be outside the repo",
        "lives outside the repo precisely",
    ),
    REQUIREMENTS_README: (
        "folder outside the consumer repo",
        "*outside* the consumer repo",
    ),
    PORTABILITY: ("outside the consumer repo, enabling worktrees",),
}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _norm(text):
    """Collapse whitespace runs to a single space, so a substring check
    isn't defeated by prose rewrapping across a line break."""
    return re.sub(r"\s+", " ", text)


def _status_line(body):
    return next((line for line in body.splitlines() if line.startswith("**Status**")), "")


class NoOutsideRepoClaimTest(unittest.TestCase):
    """AC2/AC3: no touched architecture/requirements file still makes the
    superseded 'workspace lives outside the repo' claim."""

    def test_no_stale_outside_repo_claim(self):
        for path, claims in STALE_CLAIMS.items():
            body = _norm(read(path))
            for claim in claims:
                self.assertNotIn(
                    _norm(claim), body,
                    "%s still contains stale claim %r" % (path, claim),
                )


class AdrCitationTest(unittest.TestCase):
    """AC1: ADR-0085 supersedes ADR-0003, is indexed and Accepted, and is
    cited consistently by every file that describes the workspace default."""

    def test_adr_0003_status_line_supersedes_0085(self):
        self.assertIn("Superseded by [0085]", _status_line(read(ADR_0003)))

    def test_adr_0085_exists_and_is_accepted(self):
        self.assertTrue(os.path.exists(ADR_0085), "%s not found" % ADR_0085)
        self.assertIn("Accepted", _status_line(read(ADR_0085)))

    def test_readme_indexes_0085_and_flips_0003_status(self):
        body = read(ADR_README)
        self.assertRegex(
            body,
            r"\|\s*\[0085\]\(0085-in-repo-anchored-state-machine\.md\)\s*\|",
            "docs/adr/README.md is missing the 0085 index row",
        )
        row_0003 = next((line for line in body.splitlines() if "[0003]" in line), "")
        self.assertIn("Superseded", row_0003, "0003's README row must flip to Superseded")

    def test_citing_required_files_reference_0085(self):
        for path in CITING_REQUIRED:
            self.assertRegex(
                read(path), ADR_0085_RE, "%s does not cite ADR-0085" % path,
            )


class No0084MisattributionTest(unittest.TestCase):
    """Guards the ticket-text 0084/0085 numbering confusion: every touched
    file must say '0085', never the ticket's own literal '0084' typo --
    except docs/adr/README.md, which keeps its one pre-existing, unrelated,
    real ADR-0084 row (baseline count 2: link text + display text)."""

    def test_no_0084_outside_adr_readme(self):
        for path in TOUCHED_FILES:
            if path == ADR_README:
                continue
            self.assertNotIn("0084", read(path), "%s wrongly cites 0084" % path)

    def test_adr_readme_0084_baseline_unchanged(self):
        self.assertEqual(read(ADR_README).count("0084"), 2)


class NoNewMarCitationTest(unittest.TestCase):
    """AC5: this ticket's own edits never cite '(MAR-5)', and never shift a
    touched file's pre-existing '(MAR-1)' token count away from its
    confirmed-live baseline (0 for every file not in MAR1_BASELINE)."""

    def test_no_mar5_citation(self):
        for path in TOUCHED_FILES:
            self.assertNotIn("(MAR-5)", read(path), "%s wrongly cites (MAR-5)" % path)

    def test_mar1_token_count_matches_baseline(self):
        for path in TOUCHED_FILES:
            expected = MAR1_BASELINE.get(path, 0)
            actual = len(MAR1_TOKEN_RE.findall(read(path)))
            self.assertEqual(
                actual, expected,
                "%s: MAR-1 token count %d != baseline %d" % (path, actual, expected),
            )


if __name__ == "__main__":
    unittest.main()
