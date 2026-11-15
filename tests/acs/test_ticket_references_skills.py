"""ADR-0140: the skills read a ticket's documents from the standard layout.

The deterministic layer finds the documents (`acs_lib.doc_links`) and hands them
to every skill as `context.references`; these pins hold the prose that tells a
coordinator to READ that list instead of searching the repo, and the steps of
create-ticket, breakdown-ticket and merge-pr that store the list on a ticket and
put it in the tracker. Every pin reads a skill's contract text (SKILL.md with its
own `references/` inlined), so a sentence may move between those files freely,
and whitespace is collapsed so a re-wrap never breaks one.

Run:  python3 -m unittest tests.acs.test_ticket_references_skills -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
sys.path.insert(0, os.path.join(REPO_ROOT, "tests", "acs"))
from skill_text import skill_contract  # noqa: E402

#: The one Start line every hooked skill that runs on a ticket carries.
START_LINE = ("**References: `context.references` lists this run's documents found in the "
              "standard layout — read the ones relevant to this step before working; never "
              "search the repo for them.**")

#: The hooked skills that run on a ticket (code's line lives in the protocol
#: its four delivery-path legs share, `code/references/protocol.md`).
TICKET_SKILLS = (
    "analyze-requirements", "create-impl-plan", "create-test-docs", "code", "review-code",
    "create-e2e-tests", "docs-sync", "create-api-contract", "create-data-design",
    "create-flows", "create-tech-design", "breakdown-ticket",
)

#: The ones that spawn subagents: they also say where those agents find the list.
SPAWNING = tuple(s for s in TICKET_SKILLS if s != "breakdown-ticket")


def norm(text):
    return re.sub(r"\s+", " ", text)


def read(*parts):
    with open(os.path.join(PLUGIN, *parts), encoding="utf-8") as fh:
        return fh.read()


class StartLineTest(unittest.TestCase):

    def test_every_ticket_skill_carries_the_shared_start_line(self):
        for name in TICKET_SKILLS:
            with self.subTest(skill=name):
                self.assertIn(START_LINE, norm(skill_contract(name)))

    def test_the_line_is_said_once_per_skill(self):
        for name in TICKET_SKILLS:
            with self.subTest(skill=name):
                self.assertEqual(norm(skill_contract(name)).count(START_LINE), 1)

    def test_spawning_skills_pass_the_list_to_their_subagents(self):
        for name in SPAWNING:
            with self.subTest(skill=name):
                self.assertIn("Subagents get the same list as `requirements.md`'s "
                              "`## References`; name the relevant ones in their `<inputs>`.",
                              norm(skill_contract(name)))

    def test_code_says_it_in_the_protocol_its_legs_share(self):
        self.assertIn(START_LINE, norm(read("skills", "code", "references", "protocol.md")))


class CreateTicketTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.skill = norm(skill_contract("create-ticket"))
        cls.reviewer = norm(read("agents", "create-ticket-reviewer.md"))

    def test_the_author_gets_the_references_of_the_features(self):
        self.assertIn("`<context name=\"references\">`: the JSON of `acs.py ticket references "
                      "--features <slugs> --fetch`, run once Step 1 knows the features", self.skill)
        self.assertIn("and the same references. It writes `iter-<n>/reviewer.md`", self.skill)
        for kind in ("epic", "story", "task", "bug"):
            with self.subTest(author=kind):
                author = norm(read("agents", "create-ticket-%s-author.md" % kind))
                self.assertIn('a `<context name="references">` lists the documents found', author)
                self.assertIn("leave the template's `## References` markers alone", author)

    def test_the_author_cites_only_listed_documents_and_leaves_the_markers(self):
        self.assertIn("Cite only documents in that list or named by the requirements", self.skill)
        self.assertIn("never write a link list there yourself, and never delete the markers",
                      self.skill)

    def test_the_reviewer_flags_invented_references_and_edited_markers(self):
        self.assertIn("is an invented reference — a finding", self.reviewer)
        self.assertIn("an edited, filled or deleted marker pair is a finding", self.reviewer)

    def test_the_confirmation_shows_the_list_with_pending_entries_marked(self):
        self.assertIn("6. **References**: show the documents found (title, kind, link), each "
                      "pending one marked `pending: not on <default> yet`", self.skill)

    def test_the_minted_ticket_stores_its_references(self):
        self.assertIn('acs.py" ticket references --ticket <id> --write', self.skill)

    def test_the_template_check_requires_the_references_section(self):
        self.assertIn("**The `## References` section is required** (ADR-0140)", self.skill)

    def test_an_import_is_refreshed_never_synced(self):
        self.assertIn("tracker refresh --ticket <id>` instead of a sync — **non-critical**",
                      self.skill)

    def test_the_sync_keeps_the_issue_url(self):
        self.assertIn("--key <key> --url <url>`", self.skill)

    def test_the_sync_fills_the_block(self):
        self.assertIn("**Every issue gets its `## References` section** (ADR-0140)", self.skill)


class BreakdownTicketTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.skill = norm(skill_contract("breakdown-ticket"))

    def test_each_child_stores_its_references(self):
        self.assertIn('acs.py" ticket references --ticket <child-id> --write', self.skill)
        self.assertIn("the parent epic's design records included", self.skill)

    def test_each_child_gets_a_tracker_body_before_the_sync(self):
        self.assertIn("**Write each child's body first**", self.skill)
        self.assertIn("<child partition>/tracker-body.md", self.skill)
        # Before the sync call it precedes, not after.
        body = self.skill.index("**Write each child's body first**")
        self.assertLess(self.skill.index("references/tracker-sync.md"), body)

    def test_the_epic_is_refreshed_not_re_created(self):
        self.assertIn("`acs.py tracker refresh --ticket <id>` (non-critical", self.skill)


class MergePrTest(unittest.TestCase):

    def test_a_merge_refreshes_pending_references_best_effort(self):
        skill = norm(skill_contract("merge-pr"))
        self.assertIn('acs.py" tracker refresh --pending', skill)
        self.assertIn("4b. **Refresh pending references** (ADR-0140)", skill)
        self.assertIn("nor is a failed step-4b refresh, which is only an `info` finding", skill)
        self.assertIn("references refreshed", skill)


if __name__ == "__main__":
    unittest.main()
