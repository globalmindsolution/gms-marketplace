"""/acs:set-doc-status and PRD versioning (ADR-0130).

Pins the contract of the document-status utility skill -- an UNHOOKED,
inline skill that lists the versioned documents with `acs.py design list`,
asks ONE grouped multi-select question, and moves every pick at once with
`acs.py design status --set` -- and the create-prd / code passages that keep
`prd.md` and `roadmap.md` versioned: the coordinator inits or bumps them, the
author never touches the block, the reviewer exempts it from the
byte-for-byte rule but demands a bumped version, and the code implementer's
factual edits bump.

The listing test runs the real CLI over a temp repo, so the group keys and
labels the SKILL.md names are the ones `design list` prints.

Run:  python3 -m unittest tests.acs.test_set_doc_status_skill -v
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
ACS = os.path.join(SCRIPTS, "acs.py")
SKILL = os.path.join(PLUGIN, "skills", "set-doc-status", "SKILL.md")
PRD_SKILL = os.path.join(PLUGIN, "skills", "create-prd", "SKILL.md")
PRD_AUTHOR = os.path.join(PLUGIN, "agents", "create-prd-author.md")
PRD_REVIEWER = os.path.join(PLUGIN, "agents", "create-prd-reviewer.md")
EXECUTE = os.path.join(PLUGIN, "skills", "code", "references", "execute.md")
IMPLEMENTER = os.path.join(PLUGIN, "agents", "code-implementer.md")
sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import acs_lib  # noqa: E402
from skill_text import skill_contract  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(text):
    return re.sub(r"\s+", " ", text)


def frontmatter(text):
    parts = text.split("---\n", 2)
    return parts[1], parts[2]


class SetDocStatusRegistryTest(unittest.TestCase):

    def test_it_is_an_unhooked_utility(self):
        self.assertIn("set-doc-status", acs_lib.UNHOOKED_SKILLS)
        self.assertNotIn("set-doc-status", acs_lib.HOOKED_SKILLS)
        self.assertNotIn("set-doc-status", acs_lib.skill_legs())

    def test_it_is_never_a_pipeline_step(self):
        wf = acs_lib.validate_workflow_file(acs_lib.default_workflow_path())
        self.assertFalse(acs_lib.has_step(wf, "set-doc-status"))

    def test_it_owns_no_agents(self):
        self.assertNotIn("set-doc-status", acs_lib.skill_agents())
        agents = os.listdir(os.path.join(PLUGIN, "agents"))
        self.assertEqual([a for a in agents if a.startswith("set-doc-status-")], [])

    def test_no_lifecycle_scripts(self):
        for name in ("pre-set-doc-status.py", "post-set-doc-status.py"):
            self.assertFalse(os.path.exists(os.path.join(SCRIPTS, name)), name)


class SetDocStatusSkillTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fm, cls.body = frontmatter(read(SKILL))
        cls.flat = norm(cls.body)

    def test_frontmatter(self):
        self.assertRegex(self.fm, r"(?m)^name: set-doc-status$")
        self.assertIn('argument-hint: "[status] [feature|doc…] [--reason TEXT]"', self.fm)
        desc = re.search(r"(?m)^description: (.*)$", self.fm).group(1)
        for word in ("Approve", "deprecate", "implemented", "reopen", "PRD",
                     "LLD", "Call it as your first action"):
            self.assertIn(word, desc)

    def test_lists_then_moves_through_the_cli_only(self):
        self.assertIn('acs.py" design list', self.body)
        self.assertIn('acs.py" design status --set <target>', self.body)
        self.assertIn('[--by "<name>"] [--reason "<reason>"]', self.body)
        self.assertNotIn('acs.py" step start', self.body)
        self.assertIn("never by editing the block", self.flat)

    def test_one_grouped_multi_select_ask_paged_at_four(self):
        self.assertIn("ONE AskUserQuestion, `multiSelect: true`", self.flat)
        self.assertIn("more than 4 groups, split it into pages", self.flat)
        self.assertIn("Always show the status and the version", self.flat)

    def test_target_status_comes_from_allowed_approved_first(self):
        self.assertIn("`allowed`", self.body)
        self.assertIn("`approved` first when any selected document is `proposed`", self.flat)
        self.assertIn("A move to `deprecated` needs one", self.flat)

    def test_arguments_skip_the_asks(self):
        self.assertIn("skip Steps 3 and 4 entirely", self.flat)

    def test_atomic_and_no_one_by_one_retry(self):
        self.assertIn("writes none of them when any one is refused", self.flat)
        self.assertIn("never retry the documents one by one", self.flat)

    def test_no_commit_points_at_create_pr(self):
        self.assertIn("ADR-0127", self.body)
        self.assertIn("/acs:create-pr", self.body)
        self.assertNotRegex(self.body, r"git (add|commit|push)\b")

    def test_completion_report_has_the_standard_labels(self):
        report = self.body[self.body.index("## Completion report (normative)"):]
        labels = re.findall(r"- \*\*(\w+)\*\*:", report)
        self.assertEqual(labels, ["Scope", "Status", "Results", "Findings",
                                  "Artifacts", "Metrics", "Next"])

    def test_the_group_names_it_quotes_are_the_ones_the_cli_prints(self):
        """`design list` over a repo with a PRD, a feature analysis, the HLD and
        a feature's LLD prints the keys and labels the SKILL.md tells the
        coordinator to offer and to match arguments against."""
        root = tempfile.mkdtemp(prefix="acs-set-doc-status-")
        try:
            def doc(rel, front):
                path = os.path.join(root, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("---\n%s---\n\n# T\n" % front)
            plain = "status: proposed\nversion: 1\ntickets: []\n"
            doc("docs/product/prd.md", plain)
            doc("docs/product/roadmap.md", plain)
            doc("docs/product/features/wishlist/analysis.md", plain + "feature: wishlist\n")
            doc("docs/architecture/hld/tech-stack.md", plain)
            doc("docs/architecture/lld/wishlist/api/wishlist-api.md", plain + "feature: wishlist\n")
            out = subprocess.run([sys.executable, ACS, "design", "list", "--root", root],
                                 capture_output=True, text=True, cwd=root)
            self.assertEqual(out.returncode, 0, out.stderr)
            groups = json.loads(out.stdout)["groups"]
        finally:
            shutil.rmtree(root, True)
        seen = {(g["phase"], g["key"], g["label"]) for g in groups}
        self.assertEqual(seen, {
            ("discovery", "prd", "PRD"),
            ("discovery", "prd/features/wishlist", "feature wishlist"),
            ("design", "hld", "HLD"),
            ("design", "lld/wishlist", "LLD wishlist"),
        })
        for label in ("`PRD`", "`feature <f>\nanalysis`", "`HLD`", "`LLD <f>`"):
            self.assertIn(norm(label), self.flat)
        prd = [g for g in groups if g["key"] == "prd"][0]
        self.assertEqual(prd["docs"][0]["allowed"], ["approved", "deprecated"])


class CreatePrdVersioningTest(unittest.TestCase):
    """Read as create-prd's contract: the Versions steps moved to
    `references/versions.md` and the floor to `references/review-slices.md`,
    each inlined where SKILL.md points at it."""

    def test_the_coordinator_inits_new_and_bumps_changed(self):
        body = skill_contract("create-prd")
        self.assertIn("### Versions — after every author result", read(PRD_SKILL))
        self.assertIn("### Versions — after every author result", body)
        self.assertIn('design init --status proposed "<file>"', body)
        self.assertIn('acs.py design bump "<file>"', body)
        self.assertIn("versions-before.json", body)
        self.assertIn("one run is one version", norm(body))

    def test_design_check_is_in_the_floor(self):
        body = skill_contract("create-prd")
        floor = body[body.index("**The floor, in the reviewer's own commands**"):
                     body.index("**Pass rule for sliced reviewers:**")]
        self.assertIn('acs.py" design check "<prd>" "<roadmap>"', floor)

    def test_the_author_never_touches_the_block(self):
        flat = norm(read(PRD_AUTHOR))
        self.assertIn("The leading front-matter block is exempt from the byte-for-byte rule",
                      flat)
        self.assertIn("never write, edit, reorder or remove it", flat)

    def test_the_reviewer_exempts_the_block_but_wants_a_bump(self):
        body = read(PRD_REVIEWER)
        dim8 = norm(body[body.index("8. **Amend-mode diff discipline**"):
                         body.index("9. **Iteration 2+ regression check**")])
        self.assertIn("The leading front-matter block is exempt", dim8)
        self.assertIn("A changed document whose version did not move is a finding", dim8)
        dim10 = norm(body[body.index("10. **structure**"):body.index("11. **audience-style**")])
        self.assertIn("acs.py design check <prd> <roadmap>", dim10)


class CodeFactualEditsBumpTest(unittest.TestCase):

    def test_execute_and_the_implementer_bump_an_edited_prd(self):
        for path in (EXECUTE, IMPLEMENTER):
            flat = norm(read(path))
            with self.subTest(path=os.path.basename(path)):
                self.assertIn("acs.py\" design bump [--ticket <id>]", flat)
                self.assertIn("A factual edit is a new version", flat)


if __name__ == "__main__":
    unittest.main()
