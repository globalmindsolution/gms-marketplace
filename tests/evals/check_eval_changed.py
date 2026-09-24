"""scripts/eval_changed.py -- the hook that runs the evals a change moves.

Selection is checked against the REAL case files. Running is checked against a
fake `claude` on PATH that writes the `--json` result the real CLI would, so
nothing here spends anything. Local-only like everything under tests/evals/
(ADR-0108): never loaded by CI.
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import eval_cases as ec  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "eval_changed", os.path.join(REPO_ROOT, "scripts", "eval_changed.py"))
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)

CASES = {c.name: c for c in ec.all_cases()}
PR_CHANGE = (["plugins/acs/skills/create-pr/SKILL.md"], {"create-pr"})
#: The must-never cases a create-pr description change selects.
PR_MUST_NEVER = [c.name for c in hook.select(*PR_CHANGE) if c.kind in ("negative", "control")]


def names(selected):
    return [c.name for c in selected]


class SelectionTest(unittest.TestCase):

    def test_a_description_change_selects_that_skill_and_what_names_it_only(self):
        got = names(hook.select(*PR_CHANGE))
        own = sorted(n for n, c in CASES.items()
                     if c.skill == "create-pr" and c.kind == "description")
        self.assertEqual(len(own), 3)
        for name in own:
            self.assertIn(name, got)
        borrowing = [n for n, c in CASES.items() if "confusable" in c.tags
                     and "/acs:create-pr " in c.fm.get("description", "")]
        self.assertTrue(borrowing, "some confusable case names create-pr as its neighbour")
        for name in borrowing:
            self.assertIn(name, got)
        self.assertIn("ignores-general-pr-advice", got, "the control that names create-pr")
        for name in ("route-merge-pr", "ignores-regex-request", "route-code-small-negative"):
            self.assertNotIn(name, got, "a case about another skill is not run")

    def test_a_legs_negative_runs_when_the_leg_or_its_entry_point_changes(self):
        self.assertEqual(names(hook.select(["plugins/acs/skills/code-small/SKILL.md"],
                                           {"code-small"})), ["route-code-small-negative"])
        got = names(hook.select(["plugins/acs/skills/code/SKILL.md"], {"code"}))
        for leg in ("small", "standard", "complex", "trivial"):
            self.assertIn("route-code-%s-negative" % leg, got)

    def test_a_skill_named_is_not_a_longer_skill_named(self):
        case = CASES["route-code-small-negative"]
        self.assertTrue(hook.names_skill(case, "code"))
        self.assertFalse(hook.names_skill(case, "code-s"))

    def test_no_skill_change_runs_the_full_suite(self):
        """The whole suite is the release gate's; a change runs a slice of it."""
        routing = [c for c in CASES.values() if c.group == "routing"]
        for skill in sorted(os.listdir(os.path.join(REPO_ROOT, "plugins", "acs", "skills"))):
            with self.subTest(skill=skill):
                got = hook.select(["plugins/acs/skills/%s/SKILL.md" % skill], {skill})
                self.assertLess(len([c for c in got if c.group == "routing"]), len(routing) // 5)
                self.assertFalse({"ignores-regex-request", "ignores-unrelated-request"}
                                 & set(names(got)), "the controls naming no skill are release-only")

    def test_must_never_cases_run_first(self):
        got = hook.select(*PR_CHANGE)
        kinds = [c.kind for c in got]
        first_other = next(i for i, k in enumerate(kinds) if k not in ("negative", "control"))
        self.assertTrue(all(k not in ("negative", "control") for k in kinds[first_other:]))

    def test_explicit_cases_are_not_selected_by_a_description_change(self):
        got = hook.select(["plugins/acs/skills/update/SKILL.md"], {"update"})
        self.assertNotIn("route-update-explicit", names(got))

    def test_a_body_only_change_selects_the_behaviour_suite_not_routing(self):
        got = hook.select(["plugins/acs/skills/setup/SKILL.md"], set())
        self.assertEqual({c.group for c in got}, {"setup"})
        self.assertEqual(len(got), len([c for c in CASES.values() if c.group == "setup"]))

    def test_a_skill_without_a_behaviour_suite_and_an_unchanged_description_selects_nothing(self):
        self.assertEqual(hook.select(["plugins/acs/skills/merge-pr/SKILL.md"], set()), [])

    def test_an_edited_case_is_listed_not_run(self):
        paths = ["plugins/acs/evals/routing/route-code/prompt.md",
                 "plugins/acs/evals/setup/_fixtures/python-repo.sh"]
        self.assertEqual(hook.select(paths, set()), [])
        self.assertEqual(hook.edited_cases(paths, []), ["route-code"])

    def test_an_edited_case_the_skill_change_runs_is_not_listed(self):
        paths = ["plugins/acs/skills/code/SKILL.md", "plugins/acs/evals/routing/route-code/prompt.md"]
        selected = hook.select(paths, {"code"})
        self.assertIn("route-code", names(selected))
        self.assertEqual(hook.edited_cases(paths, selected), [])

    def test_a_file_a_skill_owns_outside_its_directory_selects_its_suite(self):
        self.assertEqual({c.group for c in hook.select(
            ["plugins/acs/hooks/scripts/setup_wizard.py"], set())}, {"setup"})

    def test_the_shared_hook_library_is_not_a_skill_change(self):
        self.assertEqual(hook.select(["plugins/acs/hooks/scripts/acs_lib/tickets.py",
                                      "plugins/acs/hooks/scripts/acs.py"], set()), [])

    def test_an_unrelated_change_selects_nothing(self):
        self.assertEqual(hook.select(["README.md", "docs/adr/README.md"], set()), [])


FAKE_CLAUDE = r"""#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
case = args[args.index("--case") + 1]
path = args[args.index("--json") + 1]
runs = int(args[args.index("--runs") + 1])
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(" ".join(args) + "\n")
mode = json.loads(os.environ.get("FAKE_MODE", "{}")).get(case, "1" * runs)
if mode == "untrusted":
    sys.stderr.write("Error: plugins/acs is not a trusted plugin directory, and this run cannot stop to ask you\n")
    sys.exit(1)
arm = [{"score": None if ch == "n" else 1 if ch == "1" else 0, "turns": 0 if ch == "x" else 1,
        "error": "exit 1: usage limit reached" if ch == "x" else None,
        "graders": [{"name": "g", "passed": ch == "1", "scored": True}]}
       for ch in (mode if mode != "ceiling" else "1" * runs)]
result = {"schemaVersion": 1, "costUsd": 0.05, "partial": mode == "ceiling",
          "partialReason": "cost_ceiling" if mode == "ceiling" else None,
          "cases": [{"name": case, "arms": {"with": arm}}]}
with open(path, "w") as fh:
    json.dump(result, fh)
"""


def own(skill):
    return sorted(n for n, c in CASES.items() if c.skill == skill and c.kind == "description")


class RunTest(unittest.TestCase):
    """main() end to end with a fake CLI; the diff is stubbed, the cases are real."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        fake = os.path.join(self.tmp, "claude")
        with open(fake, "w") as fh:
            fh.write(FAKE_CLAUDE)
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
        self.log = os.path.join(self.tmp, "calls.log")
        self.env = {"FAKE_LOG": self.log}  # ACS_EVALS unset: on by default
        saved = {k: os.environ.get(k) for k in ("PATH", "FAKE_LOG", "FAKE_MODE")}
        os.environ["PATH"] = self.tmp + os.pathsep + os.environ.get("PATH", "")
        os.environ["FAKE_LOG"] = self.log

        def restore():
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.addCleanup(restore)
        stubs = {"base_ref": lambda preferred: "main",
                 "changes": lambda base, head: PR_CHANGE,
                 "configured": lambda key, default, kind: default}
        for name, fn in stubs.items():
            original = getattr(hook, name)
            setattr(hook, name, fn)
            self.addCleanup(setattr, hook, name, original)

    def main(self, modes=None, *argv):
        os.environ["FAKE_MODE"] = json.dumps(modes or {})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = hook.main(list(argv), env=self.env)
        return code, out.getvalue()

    def calls(self):
        with open(self.log) as fh:
            return [line.split() for line in fh]

    def test_everything_routing_passes(self):
        code, out = self.main({})
        self.assertEqual(code, 0, out)
        self.assertIn("acs-evals: PASS", out)

    def test_each_call_is_three_parallel_runs_guarded_and_never_trusts_for_you(self):
        self.main({})
        for call in self.calls():
            self.assertEqual(call[call.index("--runs") + 1], "3")
            self.assertEqual(call[call.index("-j") + 1], "3")
            self.assertIn("--max-cost-usd", call)
            self.assertIn("--no-publish", call)
            self.assertNotIn("--trust-plugin", call)

    def test_one_misroute_of_a_negative_blocks(self):
        code, out = self.main({PR_MUST_NEVER[0]: "110"})
        self.assertEqual(code, 1)
        self.assertIn("%s (" % PR_MUST_NEVER[0], out)
        self.assertIn("misrouted in 1 of 3 runs", out)

    def test_a_touched_skill_below_two_thirds_blocks(self):
        names = own("create-pr")
        code, out = self.main({names[0]: "100", names[1]: "100", names[2]: "111"})
        self.assertEqual(code, 1)
        self.assertIn("create-pr routed 5 of 9", out)

    def test_a_touched_skill_at_exactly_two_thirds_passes(self):
        names = own("create-pr")
        code, out = self.main({n: "110" for n in names})
        self.assertEqual(code, 0, out)

    def test_a_neighbour_that_loses_its_confusable_case_blocks(self):
        """create-pr's new description pulling merge-pr's confusable request
        away from merge-pr is exactly the regression this selection exists for."""
        borrowing = [n for n, c in CASES.items() if "confusable" in c.tags
                     and "/acs:create-pr " in c.fm.get("description", "")]
        code, out = self.main({borrowing[0]: "000"})
        self.assertEqual(code, 1)
        self.assertIn("routed 0 of 3", out)

    def test_behaviour_and_explicit_misses_are_reported_not_blocking(self):
        hook.changes, saved = (lambda base, head: (["plugins/acs/skills/setup/SKILL.md"], set())), hook.changes
        self.addCleanup(setattr, hook, "changes", saved)
        setup_case = sorted(n for n, c in CASES.items() if c.group == "setup")[0]
        code, out = self.main({setup_case: "100"})
        self.assertEqual(code, 0, out)
        self.assertIn("report: %s: 1 of 3 runs passed" % setup_case, out)

    def test_a_usage_limit_mid_run_blocks_rather_than_passing_a_negative(self):
        code, out = self.main({PR_MUST_NEVER[0]: "1x1"})
        self.assertEqual(code, 1)
        self.assertIn("never reached the model", out)

    def test_an_untrusted_directory_blocks_once_with_the_fix(self):
        code, out = self.main({PR_MUST_NEVER[0]: "untrusted"})
        self.assertEqual(code, 1)
        self.assertIn("not trusted yet", out)
        self.assertEqual(len(self.calls()), 1, "it stops after the first untrusted run")

    def test_a_run_without_a_score_blocks(self):
        code, out = self.main({PR_MUST_NEVER[0]: "1n1"})
        self.assertEqual(code, 1)
        self.assertIn("a run has no score", out)

    def test_a_guard_that_stops_a_gated_case_blocks(self):
        """An unmeasured must-never case is not a pass."""
        code, out = self.main({}, "--budget", "0.12")
        self.assertEqual(code, 1, out)
        self.assertIn("guard reached; not run:", out)
        self.assertIn("before these gated cases ran", out)
        self.assertLessEqual(len(self.calls()), 3)

    def test_the_cli_hitting_its_ceiling_on_a_gated_case_blocks(self):
        code, out = self.main({PR_MUST_NEVER[0]: "ceiling"})
        self.assertEqual(code, 1, out)
        self.assertIn("before these gated cases ran: %s" % PR_MUST_NEVER[0], out)

    def test_a_guard_that_stops_only_behaviour_cases_is_reported(self):
        hook.changes, saved = (lambda base, head: (["plugins/acs/skills/setup/SKILL.md"], set())), hook.changes
        self.addCleanup(setattr, hook, "changes", saved)
        code, out = self.main({}, "--budget", "0.07")
        self.assertEqual(code, 0, out)
        self.assertIn("guard reached; not run:", out)
        self.assertNotIn("gated cases", out)

    def test_a_change_to_no_skill_runs_nothing_and_lists_the_edited_cases(self):
        hook.changes, saved = (lambda base, head: (
            ["plugins/acs/evals/routing/route-code/prompt.md"], set())), hook.changes
        self.addCleanup(setattr, hook, "changes", saved)
        code, out = self.main({})
        self.assertEqual(code, 0, out)
        self.assertIn("1 edited case(s) not run", out)
        self.assertIn("nothing to run", out)
        self.assertFalse(os.path.exists(self.log), "the CLI is never called")

    def test_without_claude_it_lets_the_push_through(self):
        os.environ["PATH"] = os.pathsep.join(p for p in os.environ["PATH"].split(os.pathsep)
                                             if p != self.tmp and not os.path.isfile(os.path.join(p, "claude")))
        code, out = self.main({})
        self.assertEqual(code, 0)
        self.assertIn("skipped", out)


class SwitchTest(unittest.TestCase):

    def run_main(self, env, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = hook.main(list(argv), env=env)
        return code, out.getvalue()

    def test_it_never_runs_in_ci(self):
        code, out = self.run_main({"CI": "true", "ACS_EVALS": "1"})
        self.assertEqual(code, 0)
        self.assertIn("never run in CI", out)

    def test_it_can_be_turned_off(self):
        code, out = self.run_main({"ACS_EVALS": "0"})
        self.assertEqual(code, 0)
        self.assertIn("off", out)

    def test_the_env_switch_reads_the_usual_spellings(self):
        for value, expected in (("1", True), ("true", True), ("on", True), ("0", False),
                                ("false", False), ("", False)):
            with self.subTest(value=value):
                self.assertEqual(hook.enabled({"ACS_EVALS": value}), expected)

    def test_unset_means_on(self):
        saved = hook.git

        def no_config(*args):
            raise hook.subprocess.CalledProcessError(1, args)
        hook.git = no_config
        self.addCleanup(setattr, hook, "git", saved)
        self.assertTrue(hook.enabled({}))


class HookWiringTest(unittest.TestCase):
    """.pre-commit-config.yaml runs it at push and on demand -- never at commit,
    which is the stage CI's pre-commit job runs."""

    def test_the_hook_is_push_and_manual_only(self):
        with open(os.path.join(REPO_ROOT, ".pre-commit-config.yaml"), encoding="utf-8") as fh:
            text = fh.read()
        block = text[text.index("- id: acs-evals\n"):]
        block = block[:block.index("\n\n")]
        self.assertIn("entry: python3 scripts/eval_changed.py", block)
        self.assertIn("stages: [pre-push, manual]", block)
        self.assertNotIn("--trust-plugin", block)


if __name__ == "__main__":
    unittest.main()
