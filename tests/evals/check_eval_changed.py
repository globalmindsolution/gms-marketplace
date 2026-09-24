"""scripts/eval_changed.py -- the opt-in hook that runs the evals a change moves.

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
MUST_NEVER = sorted(n for n, c in CASES.items() if c.kind in ("negative", "control"))


def names(selected):
    return [c.name for c in selected]


class SelectionTest(unittest.TestCase):

    def test_a_description_change_selects_its_skill_its_neighbours_and_every_must_never(self):
        got = names(hook.select(["plugins/acs/skills/create-pr/SKILL.md"], {"create-pr"}))
        own = sorted(n for n, c in CASES.items()
                     if c.skill == "create-pr" and c.kind == "description")
        self.assertEqual(len(own), 3)
        for name in own + MUST_NEVER:
            self.assertIn(name, got)
        borrowing = [n for n, c in CASES.items() if "confusable" in c.tags
                     and "/acs:create-pr " in c.fm.get("description", "")]
        self.assertTrue(borrowing, "some confusable case names create-pr as its neighbour")
        for name in borrowing:
            self.assertIn(name, got)
        self.assertNotIn("route-merge-pr", got, "an unrelated skill's plain case is not moved")

    def test_must_never_cases_run_first(self):
        got = hook.select(["plugins/acs/skills/create-pr/SKILL.md"], {"create-pr"})
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

    def test_a_case_change_selects_that_case(self):
        got = hook.select(["plugins/acs/evals/routing/route-code/prompt.md"], set())
        self.assertEqual(names(got), ["route-code"])

    def test_a_fixture_change_selects_its_group(self):
        got = hook.select(["plugins/acs/evals/setup/_fixtures/python-repo.sh"], set())
        self.assertEqual({c.group for c in got}, {"setup"})

    def test_suite_code_selects_its_suite(self):
        self.assertEqual({c.group for c in hook.select(
            ["plugins/acs/hooks/scripts/setup_wizard.py"], set())}, {"setup"})
        self.assertEqual({c.group for c in hook.select(
            ["plugins/acs/hooks/scripts/acs_lib/tickets.py"], set())}, {"artifacts"})

    def test_an_unrelated_change_selects_nothing(self):
        self.assertEqual(hook.select(["README.md", "docs/adr/README.md"], set()), [])


FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
case = args[args.index("--case") + 1]
path = args[args.index("--json") + 1]
with open(os.environ["FAKE_LOG"], "a") as fh:
    fh.write(" ".join(args) + "\n")
mode = json.loads(os.environ.get("FAKE_MODE", "{}")).get(case, "pass")
if mode == "untrusted":
    sys.stderr.write("Error: plugins/acs is not a trusted plugin directory, and this run cannot stop to ask you\n")
    sys.exit(1)
result = {"schemaVersion": 1, "costUsd": 0.05, "partial": False, "cases": [{"name": case, "arms": {"with": [
    {"score": 1 if mode == "pass" else 0, "turns": 1, "error": None,
     "graders": [{"name": "g", "passed": mode == "pass", "scored": True}]}]}}]}
if mode == "ceiling":
    result.update(partial=True, partialReason="cost_ceiling")
with open(path, "w") as fh:
    json.dump(result, fh)
'''


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
        self.env = {"ACS_EVALS": "1", "FAKE_LOG": self.log}
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
                 "changes": lambda base, head: (["plugins/acs/skills/create-pr/SKILL.md"], {"create-pr"})}
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
        code, out = self.main({}, "--budget", "10")
        self.assertEqual(code, 0, out)
        self.assertIn("acs-evals: PASS", out)

    def test_every_call_is_one_run_capped_and_never_trusts_for_you(self):
        self.main({}, "--budget", "10")
        for call in self.calls():
            self.assertEqual(call[call.index("--runs") + 1], "1")
            self.assertIn("--max-cost-usd", call)
            self.assertIn("--no-publish", call)
            self.assertNotIn("--trust-plugin", call)

    def test_a_misrouted_negative_blocks_the_push(self):
        code, out = self.main({MUST_NEVER[0]: "fail"}, "--budget", "10")
        self.assertEqual(code, 1)
        self.assertIn(MUST_NEVER[0], out)
        self.assertIn("SKIP=acs-evals", out)

    def test_a_missed_description_case_is_reported_not_blocking(self):
        own = sorted(n for n, c in CASES.items() if c.skill == "create-pr" and c.kind == "description")
        code, out = self.main({own[0]: "fail"}, "--budget", "10")
        self.assertEqual(code, 0, out)
        self.assertIn("report: %s" % own[0], out)
        self.assertIn("one run is not evidence", out)

    def test_an_untrusted_directory_blocks_once_with_the_fix(self):
        code, out = self.main({MUST_NEVER[0]: "untrusted"}, "--budget", "10")
        self.assertEqual(code, 1)
        self.assertIn("not trusted yet", out)
        self.assertEqual(len(self.calls()), 1, "it stops after the first untrusted run")

    def test_a_budget_that_runs_out_skips_the_rest_without_blocking(self):
        code, out = self.main({}, "--budget", "0.12")
        self.assertEqual(code, 0, out)
        self.assertIn("budget reached; not run:", out)
        self.assertLessEqual(len(self.calls()), 3)

    def test_the_cli_hitting_its_ceiling_is_the_budget_not_a_failure(self):
        code, out = self.main({MUST_NEVER[0]: "ceiling"}, "--budget", "10")
        self.assertEqual(code, 0, out)
        self.assertIn("budget reached", out)


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

    def test_it_is_off_unless_turned_on(self):
        code, out = self.run_main({"ACS_EVALS": "0"})
        self.assertEqual(code, 0)
        self.assertIn("off", out)

    def test_the_env_switch_reads_the_usual_spellings(self):
        for value, expected in (("1", True), ("true", True), ("on", True), ("0", False), ("", False)):
            with self.subTest(value=value):
                self.assertEqual(hook.enabled({"ACS_EVALS": value}), expected)


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
