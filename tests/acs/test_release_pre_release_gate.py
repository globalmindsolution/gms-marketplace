"""`/acs:release` runs the repo's pre-release gate, and never cuts past it.

The gate is settings-driven, not hardcoded: the skill used to end by telling
the human to run `python3 evals/behavioural/run_evals.py --plugin acs --paid`, a path that
exists only in this marketplace and that stopped being even this repo's gate
when MAR-579 retired the per-ticket paid tier. It then read one from
`release.pre_release_gate` -- and only REMINDED the human to run it, which is
a rule nothing enforces. Now it runs every command, in order, before a fresh
cut edits anything, and the first non-zero exit ends the run.
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


class TheGateBlocksTheCutTest(unittest.TestCase):
    """Before each release the gate runs and passes; no cut proceeds past a
    failure, and nothing bypasses it."""

    def test_the_gate_runs_before_anything_is_bumped(self):
        body = read(SKILL)
        gate = body.find("Run this repo's pre-release gate")
        bump = body.find("**Bump:**")
        self.assertTrue(0 < gate < bump,
                        "the gate step must come before the first write")

    def test_the_commands_run_verbatim_and_in_order(self):
        self.assertRegex(read(SKILL), r"(?i)verbatim, in the listed order")

    def test_the_first_failure_stops_the_run(self):
        body = read(SKILL)
        self.assertRegex(body, r"(?i)first non-zero exit ends the run")
        self.assertRegex(body, r"nothing has been drafted, bumped, branched "
                               r"or pushed")

    def test_it_is_no_longer_a_reminder(self):
        self.assertNotRegex(read(SKILL),
                            r"(?i)reminder step|do not run the gate yourself|"
                            r"not a blocking check|remind(ing)? the human")

    def test_nothing_bypasses_it(self):
        body = read(SKILL)
        self.assertNotRegex(body, r"--skip-gate|--no-gate|--force-cut")
        self.assertRegex(body, r"(?i)no flag that bypasses this step")
        self.assertRegex(body, r"(?i)never skip a command, reorder them,\s+"
                               r"substitute one of your own")

    def test_a_timeout_is_not_a_pass(self):
        self.assertRegex(read(SKILL), r"(?i)timeout as a pass")

    def test_long_commands_are_waited_for_not_abandoned(self):
        body = read(SKILL)
        self.assertRegex(body, r"(?i)wait for the exit code")
        self.assertIn("echo $? >", body)

    def test_the_pr_carries_the_gate_evidence(self):
        self.assertRegex(read(SKILL), r"(?i)exit code and .{0,40}output")

    def test_the_safety_invariants_name_it(self):
        body = read(SKILL)
        inv = body[body.find("## SAFETY invariants"):body.find("## Delegation")]
        self.assertRegex(inv, r"(?i)never.{0,40}cuts past a failing gate")

    def test_the_schema_says_the_skill_runs_them(self):
        prop = release_block(json.load(open(SCHEMA)))["properties"]["pre_release_gate"]
        desc = prop["description"]
        self.assertNotIn("never runs them", desc)
        self.assertRegex(desc, r"(?i)runs .{0,80}in order")
        self.assertRegex(desc, r"(?i)first non-zero exit")


class ThisRepoDeclaresItsOwnGateTest(unittest.TestCase):

    def test_the_dogfood_repo_gates_on_the_plugin_eval_suite(self):
        gate = json.load(open(SETTINGS))["release"]["pre_release_gate"]
        self.assertTrue(gate, "this repo has a gate; it must declare it")
        joined = " ".join(gate)
        # The suite is `claude plugin eval` case files inside the plugin, so
        # the gate runs the documented CLI against THIS repo's plugin source.
        self.assertIn("claude plugin eval plugins/acs", joined)
        # The retired bespoke tooling must not come back as the gate.
        self.assertNotIn("make -C evals", joined,
                         "root evals/ was retired with its Makefile")
        self.assertNotIn("run_evals.py", joined,
                         "the behavioural harness was retired")

    def test_the_free_check_runs_before_the_paid_one(self):
        """The skill stops at the first non-zero exit, so ORDER is the cost
        control: a malformed case must fail the free validator before the
        gate spends anything on sessions that would only discover it."""
        gate = json.load(open(SETTINGS))["release"]["pre_release_gate"]
        free = [i for i, c in enumerate(gate) if "test_eval_cases" in c]
        paid = [i for i, c in enumerate(gate) if "claude plugin eval" in c]
        self.assertTrue(free and paid, gate)
        self.assertLess(free[0], paid[0])

    def test_the_paid_step_carries_a_cost_ceiling(self):
        gate = json.load(open(SETTINGS))["release"]["pre_release_gate"]
        paid = [c for c in gate if "claude plugin eval" in c]
        for command in paid:
            self.assertRegex(command, r"--max-cost-usd \d")
            self.assertIn("--trust-plugin", command,
                          "a gate cannot stop at the first-run trust prompt")

if __name__ == "__main__":
    unittest.main()
