"""MAR-587 -- the generated eval trees must be current against their sources.

`make -C src/acs-evals check` is the gate that fails when a generated tree
drifts from the curated data it is rendered from, but CI runs only
`python3 -m unittest discover -s tests`, so that gate was never read on a pull
request. These tests run the two `--check` modes inside the suite CI does run,
and pin the rendered routing tree to the skill directories this build actually
ships -- the drift that let `evals/routing/route-analyze-ticket/` keep
asserting a routing claim for a skill v0.5.0 renamed away.

No model, no network, no cost: both generators read files already on disk and
`--check` never writes.

Run:  python3 -m unittest tests.acs.test_eval_generated_trees_current -v
"""

import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVALS = os.path.join(REPO_ROOT, "src", "acs-evals")
PLUGIN = os.path.join(REPO_ROOT, "src", "acs")
ROUTING_TREE = os.path.join(EVALS, "evals", "routing")


def generator_check(script):
    """Run one generator's --check mode the way the Makefile's `check` does."""
    env = dict(os.environ, ACS_PLUGIN_ROOT=PLUGIN)
    return subprocess.run([sys.executable, os.path.join("runner", script), "--check"],
                          cwd=EVALS, env=env, capture_output=True, text=True)


def shipped_skills():
    root = os.path.join(PLUGIN, "skills")
    return {name for name in os.listdir(root)
            if os.path.isdir(os.path.join(root, name))}


def rendered_cases():
    """{case directory: (skill, tag)} read back out of the rendered YAML."""
    cases = {}
    for name in sorted(os.listdir(ROUTING_TREE)):
        path = os.path.join(ROUTING_TREE, name, "case.yaml")
        if not os.path.isfile(path):
            continue
        skill, tag = None, None
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("skill:"):
                    skill = stripped.split(":", 1)[1].strip()
                elif stripped in ("- positive", "- negative"):
                    tag = stripped[2:]
        cases[name] = (skill, tag)
    return cases


class GeneratedTreesAreCurrentTest(unittest.TestCase):
    """AC-2: `make check`'s two generator gates, run where CI can see them."""

    def test_routing_eval_tree_is_regenerated(self):
        done = generator_check("gen_plugin_eval.py")
        self.assertEqual(done.returncode, 0,
                         "evals/routing is stale or orphaned against "
                         "dataset/routing.json:\n%s%s" % (done.stdout, done.stderr))

    def test_schema_constraint_cases_are_regenerated(self):
        done = generator_check("gen_schema_cases.py")
        self.assertEqual(done.returncode, 0,
                         "dataset/cases/11-schema-constraints.json is stale "
                         "against the shipped schemas:\n%s%s"
                         % (done.stdout, done.stderr))


class RoutingTreeProbesTheShippedSurfaceTest(unittest.TestCase):
    """A rendered probe for a skill that does not ship is a claim about nothing."""

    @classmethod
    def setUpClass(cls):
        cls.cases = rendered_cases()
        cls.shipped = shipped_skills()

    def test_no_rendered_case_names_a_skill_this_build_does_not_ship(self):
        retired = sorted(name for name, (skill, _) in self.cases.items()
                         if (skill or "").split(":", 1)[-1] not in self.shipped)
        self.assertEqual(retired, [],
                         "rendered routing cases for skills with no directory "
                         "under src/acs/skills: %s" % retired)

    def test_every_shipped_skill_has_a_rendered_positive_case(self):
        covered = {(skill or "").split(":", 1)[-1]
                   for skill, tag in self.cases.values() if tag == "positive"}
        missing = sorted(self.shipped - covered)
        self.assertEqual(missing, [],
                         "shipped skills with no rendered positive routing "
                         "case: %s" % missing)


if __name__ == "__main__":
    unittest.main()
