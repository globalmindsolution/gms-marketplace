"""The shipped docs must quote the order advisory the build actually emits.

MAR-587 AC-13/AC-14. Three documents quoted or paraphrased the version-2,
`needs:`-based advisory that v0.5.0 replaced with a cursor-based line:
`docs/architecture/lld/flows/hook-gated-skill-run.md`, `src/acs/README.md`
and `docs/requirements/functional/hooks.md`. `ship.yaml` version 3 rejects
`needs:` outright (REDESIGN-IMPLEMENTATION-PIPELINE.md:1241-1248) and the
live line is built by `acs_lib/advisory.py`'s `render_advisory` (:32-37),
whose trigger is the run's cursor, not an unsatisfied dependency list
(`workflow_advisory`, :40-77).

Every expectation here is DERIVED -- from `render_advisory` and from
`workflows/ship.yaml` -- never from a second copy of the sentence. A quoted
line must be what the function builds, and the step it says the skill
"normally follows" must be the step that really precedes it in the shipped
workflow.

AC-14 -- the MAR-588-owned sites in these same three files stay
byte-unchanged -- is a property of the CHANGESET, not of the tree, so
`AdvisoryRepairStaysInItsLaneTest` asks git for the diff against the merge
base and requires every hunk in the three files to be advisory prose. It
deliberately does NOT freeze MAR-588's current wording: a test that pinned
that wording would fail the moment MAR-588 repairs it. Where git cannot
answer, it skips and the verifier's own diff is the proof.

Stdlib-only. Run:
  python3 -m unittest tests.acs.test_order_advisory_documentation -v
"""

import os
import re
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "src", "acs", "hooks", "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from acs_lib import advisory, workflow  # noqa: E402

SHIP_YAML = os.path.join(REPO_ROOT, "src", "acs", "workflows", "ship.yaml")

#: The three shipped documents that quote or describe the order advisory.
SHARED_DOCS = (
    os.path.join("docs", "architecture", "lld", "flows", "hook-gated-skill-run.md"),
    os.path.join("src", "acs", "README.md"),
    os.path.join("docs", "requirements", "functional", "hooks.md"),
)

MARK = re.escape(advisory.ADVISORY_MARK)
SKILL = r"[a-z][a-z0-9-]*"

#: A quoted line, wherever it sits: fenced, inline-code or double-quoted prose.
QUOTE_RE = re.compile(r"acs: (?P<skill>%s) %s(?P<tail>[^`\"]*)" % (SKILL, MARK))
FULL_RE = re.compile(
    r"^acs: (?P<skill>%s) %s (?P<predecessor>%s) in ship\.yaml; "
    r"the cursor for (?P<run>[A-Za-z0-9._-]+) is (?P<cursor>%s)$" % (SKILL, MARK, SKILL, SKILL))
OPENING_RE = re.compile(
    r"^acs: (?P<skill>%s) %s (?P<predecessor>%s) in ship\.yaml$" % (SKILL, MARK, SKILL))

ELLIPSIS = ("…", "...")

#: Version-2 wording, with what version 3 replaced it by.
RETIRED = (
    (re.compile(r"`needs`(?!_)"),
     "the bare `needs` construct, which ship.yaml v3 rejects "
     "(REDESIGN-IMPLEMENTATION-PIPELINE.md:1241-1248)"),
    (re.compile(r"\bneeds:"),
     "a `needs:` workflow key, which ship.yaml v3 rejects"),
    (re.compile(r"ship\.yaml needs"),
     "the step's ship.yaml needs as the advisory's trigger; the trigger is the "
     "run's cursor (advisory.py:70-72)"),
    (re.compile(r"has not completed for"),
     "the version-2 advisory tail; render_advisory names the cursor "
     "(advisory.py:32-37)"),
)

#: A hunk in a shared doc must be advisory prose -- see the module docstring.
ADVISORY_VOCABULARY = ("advisor", advisory.ADVISORY_MARK, "cursor", "acs:")


def _normalized(relative_path):
    """The document as one whitespace-collapsed string.

    Markdown word-wrap breaks a quoted advisory across two lines; a line-wise
    scan reads half a sentence and calls it clean."""
    with open(os.path.join(REPO_ROOT, relative_path), encoding="utf-8") as fh:
        return re.sub(r"\s+", " ", fh.read())


def _shipped_steps():
    doc, _lines = workflow.load_workflow(SHIP_YAML)
    return workflow.steps_of(doc)


def _quotes(relative_path):
    """Every quoted advisory line in the document, as (text, truncated)."""
    found = []
    for match in QUOTE_RE.finditer(_normalized(relative_path)):
        text = ("acs: %s %s%s" % (match.group("skill"), advisory.ADVISORY_MARK,
                                  match.group("tail"))).strip()
        truncated = text.endswith(ELLIPSIS)
        for mark in ELLIPSIS:
            if text.endswith(mark):
                text = text[:-len(mark)].strip()
        found.append((text, truncated))
    return found


def _git(args):
    """`git args` in the repo, or None when git cannot answer."""
    try:
        done = subprocess.run(["git"] + args, cwd=REPO_ROOT, check=False,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError:
        return None
    return done.stdout.decode("utf-8", "replace") if done.returncode == 0 else None


def _changed_hunks(diff):
    """The changed lines of each hunk, hunk by hunk, sign stripped."""
    hunks, current = [], None
    for line in diff.splitlines():
        if line.startswith("@@"):
            if current:
                hunks.append(current)
            current = []
        elif current is not None and line[:1] in "+-" and not line.startswith(("+++", "---")):
            current.append(line[1:])
    if current:
        hunks.append(current)
    return [hunk for hunk in hunks if hunk]


class ShippedDocsQuoteTheLiveAdvisoryTest(unittest.TestCase):
    """AC-13: the documented advisory is the one the code emits."""

    def setUp(self):
        self.steps = _shipped_steps()

    def _predecessor(self, skill, where):
        self.assertIn(skill, self.steps, "%s: %r is not a step of ship.yaml" % (where, skill))
        index = self.steps.index(skill)
        self.assertGreater(index, 0, "%s: the first step is never advised (advisory.py:74-75)" % where)
        return self.steps[index - 1]

    def test_every_quoted_advisory_is_what_render_advisory_emits(self):
        quoted = 0
        for relative_path in SHARED_DOCS:
            for text, truncated in _quotes(relative_path):
                quoted += 1
                where = "%s: %r" % (relative_path, text)
                pattern = OPENING_RE if truncated else FULL_RE
                match = pattern.match(text)
                self.assertIsNotNone(
                    match, "%s is not the shape render_advisory builds "
                           "(advisory.py:32-37)" % where)
                skill, predecessor = match.group("skill"), match.group("predecessor")
                self.assertEqual(
                    predecessor, self._predecessor(skill, where),
                    "%s names the wrong predecessor for ship.yaml v3" % where)
                if truncated:
                    opening = advisory.render_advisory(skill, "SHOP-123", predecessor, self.steps[0])
                    self.assertTrue(opening.startswith(text),
                                    "%s is not the opening of %r" % (where, opening))
                    continue
                cursor, run = match.group("cursor"), match.group("run")
                self.assertEqual(text, advisory.render_advisory(skill, run, predecessor, cursor),
                                 "%s is not byte-identical to the rendered line" % where)
                self.assertIn(cursor, self.steps, "%s names a cursor that is no step" % where)
                self.assertNotEqual(cursor, skill,
                                    "%s: a skill AT the cursor is advised of nothing "
                                    "(advisory.py:71-72)" % where)
        self.assertGreaterEqual(
            quoted, 4, "the four advisory quotes in the shared docs went missing; "
                       "deleting them is not how this is repaired")

    def test_no_shared_doc_describes_the_advisory_by_the_retired_v2_wording(self):
        for relative_path in SHARED_DOCS:
            text = _normalized(relative_path)
            for pattern, why in RETIRED:
                match = pattern.search(text)
                if match:
                    start = max(0, match.start() - 90)
                    self.fail("%s still names %s -- ...%s..."
                              % (relative_path, why, text[start:match.end() + 90]))


class AdvisoryRepairStaysInItsLaneTest(unittest.TestCase):
    """AC-14: this changeset touches nothing in the shared docs but the advisory.

    The three files also carry the sibling repair's sites (named in the module
    docstring), which must come through byte-unchanged -- which is why this is
    asked of git rather than of a frozen copy of that prose."""

    def test_only_advisory_hunks_appear_in_the_shared_docs(self):
        base = _git(["merge-base", "origin/main", "HEAD"])
        if base is None:
            self.skipTest("no origin/main merge base in this checkout")
        diff = _git(["diff", "--unified=0", base.strip(), "--"] + list(SHARED_DOCS))
        if diff is None:
            self.skipTest("git could not diff the shared docs in this checkout")
        for hunk in _changed_hunks(diff):
            blob = " ".join(hunk).lower()
            self.assertTrue(
                any(word in blob for word in ADVISORY_VOCABULARY),
                "a hunk in the shared docs changes prose that is not the order "
                "advisory; those sites belong to the sibling doc repair and must "
                "stay byte-unchanged here:\n%s" % "\n".join(hunk)[:500])


if __name__ == "__main__":
    unittest.main()
