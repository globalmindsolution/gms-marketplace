"""/acs:create-docs runs execute -> verify with no planner (ADR-0092 class D,
ADR-0094).

The four doc-set legs each ran a plan-once/execute-verify loop with a planner
whose deliverable was a plan for a template-bootstrapped document -- a second
copy of the writing. The folded skill has an executor that authors each set
and a verifier that judges it. This module pins that topology so a planner
cannot creep back in through prose, the registry, or an agent file.

Run:  python3 -m unittest tests.acs.test_create_docs_loop_topology -v
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
SKILL = os.path.join(PLUGIN, "skills", "create-docs", "SKILL.md")
AGENTS = os.path.join(PLUGIN, "agents")
sys.path.insert(0, os.path.join(PLUGIN, "hooks", "scripts"))

import acs_lib  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def norm(text):
    return re.sub(r"\s+", " ", text)


def contract():
    """The skill's contract: SKILL.md plus the references it points at.

    The resume/handoff seam moved into `references/resume-and-handoff.md` --
    a fresh run that finishes in one session never reads it. The pin is that
    the rule EXISTS, not which file states it.
    """
    import glob
    parts = [read(SKILL)]
    refs = os.path.join(PLUGIN, "skills", "create-docs", "references", "*.md")
    parts.extend(read(q) for q in sorted(glob.glob(refs)))
    return "\n".join(parts)


class NoPlannerTest(unittest.TestCase):

    def test_the_registry_declares_executor_and_verifier_only(self):
        self.assertEqual(acs_lib.skill_agents()["create-docs"], ["executor", "verifier"])

    def test_the_two_agent_files_exist_and_no_planner_does(self):
        self.assertTrue(os.path.isfile(os.path.join(AGENTS, "create-docs-executor.md")))
        self.assertTrue(os.path.isfile(os.path.join(AGENTS, "create-docs-verifier.md")))
        self.assertFalse(os.path.exists(os.path.join(AGENTS, "create-docs-planner.md")))
        for leg in ("quality", "operations", "principles", "standards"):
            for role in ("planner", "executor", "verifier"):
                self.assertFalse(os.path.exists(os.path.join(AGENTS, "create-%s-%s.md" % (leg, role))),
                                 "the leg agent files were folded away")

    def test_the_prose_never_spawns_a_planner(self):
        body = read(SKILL)
        self.assertNotIn("acs:create-docs-planner", body)
        self.assertNotRegex(body, r"(?i)spawn (exactly )?one .{0,40}planner")
        self.assertNotIn("iter-1-plan.md", body)
        self.assertNotIn("iter-<n>-plan.md", body)

    def test_the_prose_says_there_is_no_plan_phase(self):
        body = norm(read(SKILL))
        self.assertRegex(body, r"(?i)execute → verify, no planner")
        self.assertRegex(body, r"(?i)There is no plan phase")


class ExecuteVerifyLoopTest(unittest.TestCase):

    def test_cap_is_three_execute_verify_rounds(self):
        body = norm(read(SKILL))
        self.assertRegex(body, r"(?i)execute → verify, max 3 iterations")
        self.assertRegex(body, r"(?i)an iteration counts:\*\* one execute → verify round")

    def test_iteration_one_authors_and_later_ones_remediate(self):
        body = norm(read(SKILL))
        self.assertRegex(body, r"(?i)iteration 1'?s executor reads the upstream inputs, decides the mode, authors the set")
        self.assertRegex(body, r"(?i)findings go verbatim into the next executor `<task>` `<context>`")

    def test_the_executor_writes_authoring_notes_and_the_verifier_reads_them(self):
        skill = read(SKILL)
        self.assertIn("iter-<n>-authoring.md", skill)
        executor = read(os.path.join(AGENTS, "create-docs-executor.md"))
        self.assertIn("iter-<n>-authoring.md", executor)
        self.assertIn("- **Upstream inventory**", executor)
        verifier = read(os.path.join(AGENTS, "create-docs-verifier.md"))
        self.assertIn("iter-<n>-authoring.md", verifier)
        self.assertRegex(verifier, r"(?m)^4\.\s+\*\*authoring-conformance\*\*")

    def test_the_set_travels_in_constraints_not_in_agent_names(self):
        for name in ("create-docs-executor.md", "create-docs-verifier.md"):
            body = read(os.path.join(AGENTS, name))
            self.assertIn("`doc_set`", body)
            self.assertRegex(norm(body), r"(?i)the same agent file serves every set")

    def test_resume_never_reintroduces_a_plan_artifact(self):
        body = norm(contract())
        self.assertRegex(body, r"(?i)an execute with no verify → verify it")
        self.assertNotRegex(body, r"(?i)second planner")


class VerifierIndependenceTest(unittest.TestCase):

    def test_verifier_judges_from_artifacts_only(self):
        body = norm(read(os.path.join(AGENTS, "create-docs-verifier.md")))
        self.assertRegex(body, r"(?i)never see the executor'?s reasoning")
        self.assertRegex(body, r"(?i)NEVER rubber-stamp")

    def test_every_finding_blocks_except_the_waived_register(self):
        body = norm(read(os.path.join(AGENTS, "create-docs-verifier.md")))
        self.assertIn("ALL findings block", body)
        self.assertIn('severity="info"', body)


if __name__ == "__main__":
    unittest.main()
