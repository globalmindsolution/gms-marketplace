"""`/acs:release`'s closing reminder is settings-driven, not hardcoded.

It used to end by telling the human to run
`python3 evals/run_evals.py --plugin acs --paid`. That was wrong twice over:
the path exists only in this marketplace, and it stopped being even this
repo's gate when MAR-579 retired the per-ticket paid tier. A skill that ships
to consumer repos cannot name their gate, so it reads one from
`release.pre_release_gate` and says plainly when none is declared.
"""

import json
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SKILL = os.path.join(PLUGIN, "skills", "release", "SKILL.md")
SCHEMA = os.path.join(PLUGIN, "schemas", "settings.schema.json")
SETTINGS = os.path.join(REPO_ROOT, ".acs", "settings.json")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def release_block(schema):
    return next(b for b in schema["properties"]["release"]["oneOf"]
                if b.get("type") == "object")


class SchemaDeclaresTheSettingTest(unittest.TestCase):

    def test_pre_release_gate_is_declared_and_optional(self):
        block = release_block(json.load(open(SCHEMA)))
        self.assertIn("pre_release_gate", block["properties"])
        self.assertNotIn("pre_release_gate", block.get("required", []),
                         "a repo with no gate must still be able to release")

    def test_it_is_a_non_empty_list_of_non_empty_commands(self):
        prop = release_block(json.load(open(SCHEMA)))["properties"]["pre_release_gate"]
        self.assertEqual(prop["type"], "array")
        self.assertEqual(prop["minItems"], 1,
                         "an empty list is not a gate; omit the key instead")
        self.assertEqual(prop["items"]["minLength"], 1)


class SkillReadsItRatherThanHardcodingTest(unittest.TestCase):

    def test_the_skill_reads_the_setting(self):
        self.assertIn("pre_release_gate", read(SKILL))

    def test_the_skill_issues_no_gate_command_of_its_own(self):
        """Prose may NAME the retired command while explaining the change; it
        may not tell a reader to run one this skill invented."""
        body = read(SKILL)
        # Every fenced/inline command the reminder section offers must come
        # from settings, so no bare eval invocation may survive as an
        # instruction. The single allowed mention is the one that explains
        # what the skill stopped doing.
        mentions = re.findall(r"run_evals\.py[^\n`]*", body)
        self.assertLessEqual(
            len(mentions), 1,
            "more than one reference to the retired hardcoded gate: %r" % mentions)
        if mentions:
            context = body[max(0, body.find(mentions[0]) - 400):body.find(mentions[0])]
            self.assertRegex(
                context, r"(?i)used to hardcode|never substitute",
                "the surviving mention must be the explanation of what was "
                "removed, not a live instruction",
            )

    def test_the_skill_says_what_to_do_when_no_gate_is_declared(self):
        body = read(SKILL)
        self.assertRegex(body, r"(?i)absent.{0,200}pre_release_gate|"
                               r"pre_release_gate.{0,200}absent")


class ThisRepoDeclaresItsOwnGateTest(unittest.TestCase):

    def test_the_dogfood_repo_names_the_acs_evals_commands(self):
        gate = json.load(open(SETTINGS))["release"]["pre_release_gate"]
        self.assertTrue(gate, "this repo has a gate; it must declare it")
        joined = " ".join(gate)
        self.assertIn("src/acs-evals", joined,
                      "the gate lives at src/acs-evals since the fold")
        self.assertNotIn("run_evals.py", joined,
                         "the in-repo paid tier is an on-demand tool, not the gate")


if __name__ == "__main__":
    unittest.main()
