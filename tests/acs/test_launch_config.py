"""`.claude/launch.json` (Claude Code's preview-server config) and how /acs:setup writes it.

Covers acs_lib.launch_config (read, comment stripping, validation, candidates,
merge, plan) and the setup wizard's `detect` / `apply` wiring.

Run:  python3 -m unittest tests.acs.test_launch_config -v
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

from acs_lib import launch_config as lc  # noqa: E402

WIZARD = os.path.join(SCRIPTS, "setup_wizard.py")

WEB = {"name": "web", "runtimeExecutable": "npm", "runtimeArgs": ["run", "dev"], "port": 3000}


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acs-launch-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def put(self, rel, text):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)

    def launch(self):
        with open(lc.path(self.root), encoding="utf-8") as fh:
            return json.load(fh)


class StripCommentsTest(unittest.TestCase):
    def test_line_and_block_comments_go(self):
        text = '// top\n{"a": 1, /* mid */ "b": 2}\n'
        self.assertEqual(json.loads(lc.strip_comments(text)), {"a": 1, "b": 2})

    def test_comment_markers_inside_strings_stay(self):
        text = '{"url": "http://localhost:3000/x", "s": "a /* b */ c", "q": "x\\"//y"}'
        self.assertEqual(json.loads(lc.strip_comments(text))["url"], "http://localhost:3000/x")
        self.assertEqual(json.loads(lc.strip_comments(text))["s"], "a /* b */ c")


class ReadTest(RepoCase):
    def test_missing_file(self):
        self.assertEqual(lc.read(self.root)["exists"], False)

    def test_commented_file_reads_and_says_so(self):
        self.put(".claude/launch.json", '// keep\n{"configurations": []}')
        state = lc.read(self.root)
        self.assertEqual(state["doc"], {"configurations": []})
        self.assertTrue(state["has_comments"])

    def test_broken_file_reports_an_error(self):
        self.put(".claude/launch.json", "{nope")
        self.assertIn("not valid JSON", lc.read(self.root)["error"])


class ValidateTest(unittest.TestCase):
    def test_a_documented_configuration_is_valid(self):
        self.assertEqual(lc.validate({"version": "0.0.1", "configurations": [WEB]}), [])
        full = dict(WEB, cwd="apps/web", env={"NODE_ENV": "development"},
                    autoPort=True, url="http://localhost:3000/app")
        self.assertEqual(lc.validate_configuration(full), [])

    def test_program_is_an_alternative_to_runtime_executable(self):
        self.assertEqual(lc.validate_configuration(
            {"name": "srv", "program": "server.js", "args": ["--dev"]}), [])

    def test_each_bad_field_is_named(self):
        cases = {
            "name": {"runtimeExecutable": "npm"},
            "runtimeExecutable": {"name": "x"},
            "runtimeArgs": dict(WEB, runtimeArgs="run dev"),
            "port": dict(WEB, port=70000),
            "autoPort": dict(WEB, autoPort="yes"),
            "env": dict(WEB, env={"A": 1}),
            "url": dict(WEB, url="ftp://host"),
            "does not define": dict(WEB, command="npm run dev"),
        }
        for needle, cfg in cases.items():
            with self.subTest(field=needle):
                errors = lc.validate_configuration(cfg)
                self.assertTrue(any(needle in e for e in errors), errors)

    def test_a_url_with_credentials_is_refused(self):
        self.assertTrue(lc.validate_configuration(dict(WEB, url="http://u:p@localhost:3000")))

    def test_a_bool_is_not_a_port(self):
        self.assertTrue(lc.validate_configuration(dict(WEB, port=True)))

    def test_duplicate_names_are_refused(self):
        errors = lc.validate({"configurations": [WEB, dict(WEB)]})
        self.assertTrue(any("used twice" in e for e in errors), errors)

    def test_document_level_fields(self):
        self.assertTrue(lc.validate({"configurations": "x"}))
        self.assertTrue(lc.validate({"configurations": [], "autoVerify": "no"}))


class CandidatesTest(RepoCase):
    def test_a_vite_dev_script_with_pnpm(self):
        self.put("package.json", json.dumps({"name": "shop", "scripts": {"dev": "vite"}}))
        self.put("pnpm-lock.yaml", "")
        self.assertEqual(lc.candidates(self.root), [
            {"name": "shop", "runtimeExecutable": "pnpm", "runtimeArgs": ["run", "dev"],
             "port": 5173}])

    def test_start_is_used_when_there_is_no_dev(self):
        self.put("package.json", json.dumps({"scripts": {"start": "next start"}}))
        cand = lc.candidates(self.root)[0]
        self.assertEqual((cand["runtimeExecutable"], cand["runtimeArgs"], cand["port"]),
                         ("npm", ["run", "start"], 3000))

    def test_django_and_rails(self):
        self.put("manage.py", "")
        self.put("bin/rails", "")
        names = [c["name"] for c in lc.candidates(self.root)]
        self.assertEqual(names, ["django", "rails"])

    def test_nothing_to_guess(self):
        self.put("package.json", json.dumps({"scripts": {"test": "jest"}}))
        self.assertEqual(lc.candidates(self.root), [])

    def test_every_candidate_is_valid(self):
        self.put("package.json", json.dumps({"scripts": {"dev": "vite"}}))
        self.put("manage.py", "")
        for cand in lc.candidates(self.root):
            self.assertEqual(lc.validate_configuration(cand), [], cand)


class MergeAndPlanTest(RepoCase):
    def test_merge_adds_new_names_and_keeps_existing_ones(self):
        mine = dict(WEB, port=4000)
        doc, added, kept = lc.merge({"configurations": [mine]},
                                    [WEB, {"name": "api", "program": "s.js"}])
        self.assertEqual(added, ["api"])
        self.assertEqual(kept, ["web"])
        self.assertEqual(doc["configurations"][0]["port"], 4000, "an existing entry is never replaced")
        self.assertEqual(doc["version"], lc.VERSION)

    def test_plan_on_an_empty_repo_writes(self):
        doc, report = lc.plan(self.root, {"configurations": [WEB]})
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["added"], ["web"])
        self.assertEqual(doc["configurations"], [WEB])

    def test_plan_with_nothing_new_writes_nothing(self):
        lc.write(self.root, {"version": "0.0.1", "configurations": [WEB]})
        doc, report = lc.plan(self.root, {"configurations": [WEB]})
        self.assertIsNone(doc)
        self.assertEqual(report["kept"], ["web"])

    def test_plan_refuses_to_rewrite_a_commented_file(self):
        self.put(".claude/launch.json", '// ours\n{"configurations": []}')
        doc, report = lc.plan(self.root, {"configurations": [WEB]})
        self.assertIsNone(doc)
        self.assertTrue(any("comments" in e for e in report["errors"]))

    def test_plan_refuses_an_invalid_answer(self):
        doc, report = lc.plan(self.root, {"configurations": [{"name": "x"}]})
        self.assertIsNone(doc)
        self.assertTrue(report["errors"])

    def test_plan_warns_about_secret_looking_env(self):
        _doc, report = lc.plan(self.root, {"configurations": [dict(WEB, env={"API_TOKEN": "x"})]})
        self.assertTrue(any("API_TOKEN" in w for w in report["warnings"]))

    def test_plan_can_set_auto_verify(self):
        doc, _report = lc.plan(self.root, {"configurations": [WEB], "autoVerify": False})
        self.assertIs(doc["autoVerify"], False)


class WizardTest(RepoCase):
    def setUp(self):
        super().setUp()
        subprocess.run(["git", "init", "-q", self.root], check=True)
        self.home = tempfile.mkdtemp(prefix="acs-home-")
        self.addCleanup(shutil.rmtree, self.home, True)

    def wizard(self, *args):
        env = dict(os.environ, HOME=self.home)
        out = subprocess.run([sys.executable, WIZARD] + list(args) + ["--cwd", self.root],
                             capture_output=True, text=True, env=env)
        return json.loads(out.stdout)

    def apply(self, answers):
        p = os.path.join(self.root, "answers.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(answers, fh)
        return self.wizard("apply", "--answers", p)

    def test_detect_reports_candidates_when_there_is_no_file(self):
        self.put("package.json", json.dumps({"scripts": {"dev": "vite"}}))
        launch = self.wizard("detect")["launch"]
        self.assertFalse(launch["exists"])
        self.assertEqual(launch["candidates"][0]["port"], 5173)

    def test_detect_reports_existing_configurations_and_offers_no_guess(self):
        self.put("package.json", json.dumps({"scripts": {"dev": "vite"}}))
        lc.write(self.root, {"version": "0.0.1", "configurations": [WEB]})
        launch = self.wizard("detect")["launch"]
        self.assertEqual(launch["configurations"], ["web"])
        self.assertEqual(launch["candidates"], [])

    def test_apply_writes_it_and_stages_it(self):
        out = self.apply({"launch": {"configurations": [WEB]}})
        self.assertTrue(out["ok"], out)
        self.assertIn(".claude/launch.json", out["stage_for_commit"])
        self.assertEqual(self.launch()["configurations"], [WEB])

    def test_apply_again_changes_nothing(self):
        self.apply({"launch": {"configurations": [WEB]}})
        out = self.apply({"launch": {"configurations": [WEB]}})
        self.assertTrue(out["ok"], out)
        self.assertNotIn(".claude/launch.json", out["stage_for_commit"])

    def test_an_invalid_launch_answer_writes_nothing_at_all(self):
        out = self.apply({"settings": {"ticket_prefix": "SHOP"},
                          "launch": {"configurations": [{"name": "x"}]}})
        self.assertFalse(out["ok"])
        self.assertFalse(os.path.exists(lc.path(self.root)))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".acs", "settings.json")))

    def test_no_launch_answer_leaves_the_file_alone(self):
        out = self.apply({"settings": {"ticket_prefix": "SHOP"}})
        self.assertTrue(out["ok"], out)
        self.assertIsNone(out["launch"])
        self.assertFalse(os.path.exists(lc.path(self.root)))

    def test_a_non_object_launch_answer_is_refused(self):
        p = os.path.join(self.root, "answers.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"launch": ["web"]}, fh)
        out = subprocess.run([sys.executable, WIZARD, "apply", "--answers", p, "--cwd", self.root],
                             capture_output=True, text=True, env=dict(os.environ, HOME=self.home))
        self.assertEqual(out.returncode, 2)
        self.assertIn("'launch' must be an object", out.stderr)
        self.assertFalse(os.path.exists(lc.path(self.root)))


if __name__ == "__main__":
    unittest.main()
