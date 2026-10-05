"""ADR-0132 on the skill surface: share or keep local, and where documents go.

The deterministic half -- `acs.py docs where|decide`, the publish refusal, the
local paths -- is tested beside `acs_lib.doc_share`. This module pins what the
SKILL.md files must say so a coordinator follows it:

* every writer of a per-run document (analysis, plan, test cases, design, API
  contract) asks `docs where --doc <name>` BEFORE its first write, folds what
  `needs` names into its ONE grouped ask (share yes/no + scope user/team;
  location: proposed / another folder / keep local), saves the answer with
  `docs decide`, keeps the document local for that run only when nobody can
  answer, and names where the document went in its report;
* every writer of a living document into a folder that may not exist yet asks
  `docs where --doc living:<kind>` and asks the location question only --
  living documents are always shared;
* /acs:setup shows and changes both;
* every `--doc` name and `docs decide` flag a skill uses is one the CLI accepts.
"""

import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skill_text  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SKILLS = os.path.join(ROOT, "plugins", "acs", "skills")
ACS = os.path.join(ROOT, "plugins", "acs", "hooks", "scripts", "acs.py")

#: skill -> the per-run document it writes.
RUN_DOCS = {
    "analyze-requirements": "analysis.md",
    "create-impl-plan": "plan.md",
    "create-test-docs": "test-cases.md",
    "create-design": "design.md",
    "create-api-contract": "api-contract.md",
}
#: skill -> the living document whose folder it may be the first to create.
LIVING = {
    "create-prd": "living:prd",
    "create-architecture": "living:architecture",
    "create-data-design": "living:architecture",
    "create-flows": "living:architecture",
}
#: the four run-document writers that share one section shape.
SHARED_SECTION = "### Share or keep local — asked once, in the same grouped ask (ADR-0132)"
ANALYSIS_SECTION = "### Where the analysis goes — share or keep local, in the same ask (ADR-0132)"


def _read(skill):
    """What the skill SAYS: SKILL.md with its `references/` inlined where it
    points at them (tests/acs/skill_text.py), so a share section whose
    conditional arms moved behind a pointer is still read whole."""
    return skill_text.skill_contract(skill)


def _norm(text):
    return " ".join(text.split())


def _section(body, heading):
    start = body.index(heading)
    rest = body[start + len(heading):]
    match = re.search(r"^#{2,3} ", rest, re.M)
    return body[start:start + len(heading) + (match.start() if match else len(rest))]


def _cli_help(*args):
    out = subprocess.run([sys.executable, ACS] + list(args) + ["-h"],
                         capture_output=True, text=True)
    return out.stdout + out.stderr


class RunDocumentWritersAskFirst(unittest.TestCase):

    def _share_section(self, skill):
        body = _read(skill)
        heading = ANALYSIS_SECTION if skill == "analyze-requirements" else SHARED_SECTION
        self.assertIn(heading, body, skill)
        return body, _norm(_section(body, heading))

    def test_every_writer_asks_where_its_document_goes(self):
        for skill, doc in RUN_DOCS.items():
            with self.subTest(skill=skill):
                _body, section = self._share_section(skill)
                self.assertIn('acs.py" docs where --doc %s' % doc, section)

    def test_where_is_asked_before_the_first_write(self):
        for skill, doc in RUN_DOCS.items():
            with self.subTest(skill=skill):
                body, section = self._share_section(skill)
                if skill == "analyze-requirements":
                    # Stage 2 holds the ask; the controller publishes in Stage 3.
                    self.assertIn("Before Stage 2 asks anything", section)
                    self.assertLess(body.index("docs where --doc %s" % doc),
                                    body.index("## Stage 3"))
                else:
                    self.assertIn("Right after the artifact resolution, before "
                                  "anything is written", section)
                    self.assertIn("before Publish", section)

    def test_the_questions_join_the_one_grouped_ask(self):
        for skill in RUN_DOCS:
            with self.subTest(skill=skill):
                _body, section = self._share_section(skill)
                if skill == "analyze-requirements":
                    self.assertIn("in the SAME grouped ask, never a separate one", section)
                else:
                    self.assertIn("join this skill's ONE grouped ask", section)
                    self.assertIn("never a separate one", section)

    def test_both_questions_and_both_scopes_are_asked(self):
        for skill in RUN_DOCS:
            with self.subTest(skill=skill):
                _body, section = self._share_section(skill)
                self.assertIn("share run documents in the repo, or keep them local?", section)
                self.assertIn("`.acs/settings.local.json`", section)
                self.assertIn("`.acs/settings.json`", section)
                self.assertIn("`proposed_path`", section)
                self.assertIn("keep documents local", section)
                self.assertIn("acs never creates a new docs folder without that answer", section)
                self.assertIn('acs.py" docs decide --share yes --scope team --location', section)

    def test_a_saved_choice_is_followed_silently(self):
        for skill in RUN_DOCS:
            with self.subTest(skill=skill):
                _body, section = self._share_section(skill)
                self.assertRegex(section, r"(?i)\*\*`?needs`? empty\*\*|\*\*empty\*\*")
                self.assertIn("silently", section)
                self.assertIn("`/acs:create-pr`", section)

    def test_nobody_to_ask_means_local_for_this_run_only(self):
        for skill in RUN_DOCS:
            with self.subTest(skill=skill):
                _body, section = self._share_section(skill)
                self.assertIn("acs.py docs decide --share no --scope run", section)
                self.assertIn("nothing saved", section)

    def test_a_local_document_never_reaches_the_commit(self):
        for skill in RUN_DOCS:
            with self.subTest(skill=skill):
                body = _norm(_read(skill))
                self.assertRegex(body, r"(was|were) kept local|kept local\)|not when kept local")
                self.assertIn("/local/", body)

    def test_the_completion_report_names_where_it_went(self):
        for skill in RUN_DOCS:
            with self.subTest(skill=skill):
                body = _read(skill)
                self.assertIn("kept local (team default)", _norm(body))
                report = body[body.index("## Completion report (normative)"):]
                self.assertRegex(report, r"kept local")

    def test_a_discovery_analysis_asks_for_its_folder_only(self):
        _body, section = self._share_section("analyze-requirements")
        self.assertIn("`--doc living:prd` on a Discovery run", section)
        self.assertIn("not offered for `living:prd`", section)

    def test_stage_two_is_skipped_only_when_nothing_about_the_documents_is_open(self):
        body = _norm(_read("analyze-requirements"))
        self.assertIn("and `docs where` (Where the analysis goes, below) reports no "
                      "`needs` — Stage 2 is skipped", body)

    def test_the_publish_refuses_an_undecided_write(self):
        body = _norm(_read("analyze-requirements"))
        self.assertIn("while `docs where` still reports `needs` it exits 2 naming "
                      "`acs.py docs decide`", body)


class LivingDocumentWritersAskForTheFolder(unittest.TestCase):

    def test_every_living_writer_asks_where_its_folder_is(self):
        for skill, doc in LIVING.items():
            with self.subTest(skill=skill):
                body = _norm(_read(skill))
                self.assertIn("docs where --doc %s" % doc, body)
                kind = doc.split(":", 1)[1]
                self.assertIn("docs decide --location %s=<folder>" % kind, body)

    def test_living_documents_are_always_shared(self):
        for skill in LIVING:
            with self.subTest(skill=skill):
                body = _norm(_read(skill))
                self.assertIn("always shared", body)
                self.assertIn("no keep-local option", body)
                self.assertIn("acs never creates a new docs folder without asking", body)

    def test_the_folder_question_is_part_of_the_one_grouped_ask(self):
        for skill in LIVING:
            with self.subTest(skill=skill):
                body = _norm(_read(skill))
                self.assertRegex(body, r"ONE grouped ask")
                self.assertIn("`location_source: default`", body)


class SetupShowsAndChangesThem(unittest.TestCase):

    def test_setup_offers_the_share_default_and_the_folders(self):
        body = _norm(_read("setup"))
        self.assertIn("**Run documents and doc folders** (ADR-0132)", body)
        self.assertIn("`acs.py docs where`", body)
        self.assertIn('acs.py" docs decide --share yes|no --scope user|team', body)
        self.assertIn("`.acs/settings.local.json`", body)
        self.assertIn("`--location <kind>=<folder>`", body)

    def test_setup_reports_them(self):
        body = _read("setup")
        report = body[body.index("## Completion report (normative)"):]
        self.assertIn("run documents (shared / kept local, whose default) and doc folders", report)


class SkillsSpeakTheCliItShips(unittest.TestCase):
    """A `--doc` name or a `docs decide` flag the CLI does not accept is a
    coordinator that fails at its first step."""

    @classmethod
    def setUpClass(cls):
        cls.where_help = _cli_help("docs", "where")
        cls.decide_help = _cli_help("docs", "decide")
        cls.bodies = {s: _read(s) for s in list(RUN_DOCS) + list(LIVING) + ["setup"]}

    def test_every_doc_name_is_a_cli_choice(self):
        used = set()
        for body in self.bodies.values():
            used.update(re.findall(r"docs where --doc ([\w:.-]+)", body))
        self.assertTrue(used)
        for doc in sorted(used):
            with self.subTest(doc=doc):
                self.assertIn(doc, self.where_help)

    def test_every_decide_flag_and_scope_is_accepted(self):
        for flag in ("--share", "--scope", "--location", "--doc"):
            self.assertIn(flag, self.decide_help)
        scopes = set()
        for body in self.bodies.values():
            scopes.update(re.findall(r"--scope (\w+)", body))
        choices = re.search(r"--scope \{([\w,]+)\}", self.decide_help)
        self.assertIsNotNone(choices, self.decide_help)
        self.assertLessEqual(scopes, set(choices.group(1).split(",")))
        kinds = set()
        for body in self.bodies.values():
            kinds.update(re.findall(r"--location (\w+)=", body))
        for kind in sorted(kinds):
            with self.subTest(kind=kind):
                self.assertIn(kind, self.decide_help)


if __name__ == "__main__":
    unittest.main()
