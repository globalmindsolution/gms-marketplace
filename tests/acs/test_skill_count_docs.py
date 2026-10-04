"""Skill and agent counts in the requirements and architecture docs.

Carved out of the MAR-121 standardize-project flow-doc suite when ADR-0118
removed that skill: the count guards were never about it. Every number here
is derived from the skill and agent directories on disk, so a skill added or
retired fails these until the docs follow.

Stdlib-only. Run:
  python3 -m unittest tests.acs.test_skill_count_docs -v
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


#: The skills whose agents are NOT in a write -> judge reflection loop: code's
#: implementer, review-code's lens and adjudicator (ADR-0109), and
#: audit-design's gap analyst, a read-only survey with no writer to judge
#: (ADR-0122), and audit-security's auditor and adjudicator, which raise and
#: refute findings with no writer between them (ADR-0123). Was `agents - 3`; a
#: constant offset stopped describing the tree once a loop-less skill gained an
#: agent, so the loop agents are counted by their owning skill instead.
NON_LOOP_SKILLS = ("code", "review-code", "audit-design", "audit-security")


def loop_agent_count():
    """Agent files owned by a skill that runs a write -> judge loop."""
    names = [n[:-len(".md")] for n in os.listdir(os.path.join(PLUGIN, "agents"))
             if n.endswith(".md")]
    return len([n for n in names
                if not any(n.startswith(s + "-") for s in NON_LOOP_SKILLS)])


class SkillsMdCountAndTriadProseTest(unittest.TestCase):
    """skills.md states the skill count in words, derived from disk."""

    def _skills_req(self):
        return read(os.path.join(REPO_ROOT, "docs", "requirements", "functional", "skills.md"))

    #: The intro states the count in WORDS, so the check spells the number
    #: derived from disk rather than pinning one literal that goes stale on
    #: every skill added or retired.
    WORDS = {23: "Twenty-three", 24: "Twenty-four", 25: "Twenty-five",
             26: "Twenty-six", 27: "Twenty-seven", 28: "Twenty-eight",
             29: "Twenty-nine", 30: "Thirty", 31: "Thirty-one",
             32: "Thirty-two", 33: "Thirty-three", 34: "Thirty-four"}

    def test_intro_count_matches_the_skill_directories_on_disk(self):
        shipped = len([
            name for name in os.listdir(os.path.join(PLUGIN, "skills"))
            if os.path.isfile(os.path.join(PLUGIN, "skills", name, "SKILL.md"))
        ])
        word = self.WORDS.get(shipped)
        self.assertIsNotNone(word, "extend WORDS for %d skills" % shipped)
        body = self._skills_req()
        intro = body[:600]
        self.assertIn("%s skills" % word, intro,
                      "skills.md intro must read '%s skills'" % word)
        for other, stale in self.WORDS.items():
            if other == shipped:
                continue
            self.assertNotIn("%s skills in total" % stale, intro,
                             "skills.md intro must NOT still read %r" % stale)

    def test_models_config_bullet_reads_the_role_tiers(self):
        body = self._skills_req()
        self.assertIn("model and effort of its role's tier configured there", body)
        self.assertNotIn("the fourteen\n  reflection-loop skills only", body)
        self.assertNotIn("the twelve\n  triad-keeping skills only", body)
        self.assertNotIn("the eleven\n  triad-keeping skills only", body)
        self.assertNotIn("the six\n  triad-keeping skills only", body)


class C4CountAndListFilesTest(unittest.TestCase):
    """The C4 and tech-stack docs carry the live skill and agent counts."""

    def test_c4_container_skill_and_agent_counts(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-container.md"))
        # Derived, not pinned: a new skill directory moves the diagram
        # by itself rather than waiting for someone to notice.
        shipped = len([n for n in os.listdir(
            os.path.join(REPO_ROOT, "plugins", "acs", "skills"))
            if os.path.isdir(os.path.join(
                REPO_ROOT, "plugins", "acs", "skills", n))])
        self.assertIn("%d x SKILL.md" % shipped, body)
        self.assertNotIn("21 x SKILL.md", body)
        agents = len([n for n in os.listdir(
            os.path.join(REPO_ROOT, "plugins", "acs", "agents")) if n.endswith(".md")])
        self.assertIn("%d x agent .md (all reachable)" % agents, body)
        self.assertNotIn("43 x agent .md (all reachable)", body)
        self.assertNotIn("39 x agent .md (33 reachable)", body)

    def test_c4_component_triad_and_reachable_counts(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "c4-component.md"))
        self.assertNotIn("twelve triad-keeping skills", body)
        self.assertNotIn("eleven triad-keeping skills", body)
        agents = len([n for n in os.listdir(
            os.path.join(REPO_ROOT, "plugins", "acs", "agents")) if n.endswith(".md")])
        # Everything but code's implementer (1), review-code's lens and
        # adjudicator (2) and audit-design's gap analyst (1) belongs to a
        # reflection-loop skill (ADR-0109, ADR-0122).
        self.assertIn("**%d agents**" % loop_agent_count(), body)
        self.assertNotIn("12 authoring pairs (24 agents", body)
        self.assertNotIn("12 active triads (36 agents", body)
        self.assertIn("%d agent files, all reachable" % agents, body)
        self.assertNotIn("43 agent files, all reachable", body)
        self.assertNotIn("36 reachable agents", body)

    def test_tech_stack_skill_and_agent_counts(self):
        body = read(os.path.join(REPO_ROOT, "docs", "architecture", "hld", "tech-stack.md"))
        # Derived, not pinned: a new skill directory moves this count by
        # itself rather than waiting for someone to notice the doc is stale.
        shipped = len([n for n in os.listdir(os.path.join(REPO_ROOT, "plugins", "acs", "skills"))
                       if os.path.isdir(os.path.join(REPO_ROOT, "plugins", "acs", "skills", n))])
        self.assertIn("acs Skills (%d)" % shipped, body)
        self.assertNotIn("acs Skills (21)", body)
        agents = len([n for n in os.listdir(
            os.path.join(REPO_ROOT, "plugins", "acs", "agents")) if n.endswith(".md")])
        self.assertIn("%d files, all reachable" % agents, body)
        self.assertNotIn("43 files, all reachable", body)
        self.assertNotIn("39 files, 33 reachable", body)
        self.assertIn("the nine authoring skills (%d agents" % loop_agent_count(), body)
        self.assertNotIn("twelve authoring skills (24 agents)", body)
        self.assertNotIn("twelve triad-keeping skills (36 agents)", body)
        self.assertNotIn("eleven triad-keeping skills (33 agents)", body)

if __name__ == "__main__":
    unittest.main()
