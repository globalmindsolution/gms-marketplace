"""MAR-526: /acs:setup is a conversation over a wizard, not a recipe.

setup/SKILL.md was 1,003 lines, most of them mechanics: four shell blocks to add
one `.gitignore` line, a heredoc to write a JSON dict, three near-identical
"copy the workflow, chmod it" blocks, and a Python heredoc to upsert a managed
`CLAUDE.md` block. None of that is conversation, and all of it was re-derived on
every run — the pattern ADR 0001 exists to prevent.

**Idempotence is the contract, not a nicety.** /acs:setup is re-run whenever a
format changes, and a repo initialised by an older acs is expected to be
repaired by a re-run. So every case below is checked twice where it matters:
once on a fresh repo, once on the same repo again, asserting the second run
reports the work as `unchanged` rather than doing it twice.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = os.path.join(REPO_ROOT, "plugins", "acs")
SCRIPTS = os.path.join(PLUGIN, "hooks", "scripts")
SKILL = os.path.join(PLUGIN, "skills", "setup", "SKILL.md")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402
import setup_wizard  # noqa: E402


class WizardCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "shop")
        os.makedirs(self.repo)
        subprocess.run(["git", "init", "-q", self.repo], check=True, capture_output=True)
        subprocess.run(["git", "-C", self.repo, "remote", "add", "origin",
                        "https://github.com/acme/shop.git"], check=True, capture_output=True)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        patcher = unittest.mock.patch.dict(os.environ, {"HOME": self.home})
        patcher.start()
        self.addCleanup(patcher.stop)

    def answers(self, **over):
        doc = {"scope": "project", "settings": {"ticket_prefix": "SHOP"},
               "workspace_path": os.path.join(self.tmp, "ws")}
        doc.update(over)
        return doc

    def apply(self, answers=None, dry_run=False):
        return setup_wizard.apply(self.repo, answers or self.answers(), dry_run=dry_run)

    def read(self, *parts):
        with open(os.path.join(self.repo, *parts), encoding="utf-8") as fh:
            return fh.read()


import unittest.mock  # noqa: E402  (imported after WizardCase's use is declared)


class DetectTest(WizardCase):
    """Everything the conversation needs before it asks anything."""

    def test_a_fresh_repo_reports_no_settings_in_any_scope(self):
        out = setup_wizard.detect(self.repo)
        self.assertTrue(out["ok"])
        for scope in ("user", "project", "local"):
            self.assertFalse(out["scopes"][scope]["exists"], scope)
        self.assertEqual(out["repo_id"], "acme-shop")
        self.assertIn("shop", out["checkout_root"])

    def test_it_reports_which_scope_a_setting_came_from(self):
        """"Which scope" is the question a re-run has to answer before it can
        ask anything sensible."""
        self.apply()
        out = setup_wizard.detect(self.repo)
        self.assertTrue(out["scopes"]["project"]["exists"])
        self.assertIn("ticket_prefix", out["scopes"]["project"]["keys"])
        self.assertIn("workspace_path", out["scopes"]["local"]["keys"])

    def test_it_reports_the_ignore_state_before_anything_is_written(self):
        out = setup_wizard.detect(self.repo)
        self.assertEqual(out["ignored"], {".acs/settings.local.json": False,
                                          ".acs/state-machine/": False})

    def test_it_names_the_files_a_broad_rule_would_swallow(self):
        with open(os.path.join(self.repo, ".gitignore"), "w", encoding="utf-8") as fh:
            fh.write(".acs/\n")
        out = setup_wizard.detect(self.repo)
        self.assertEqual(sorted(out["swallowed_by_a_broad_rule"]),
                         [".acs/ci/check-conventions.py", ".acs/settings.json"])

    def test_it_suggests_test_commands_from_what_the_repo_actually_has(self):
        os.makedirs(os.path.join(self.repo, "tests"))
        open(os.path.join(self.repo, "pyproject.toml"), "w").close()
        commands = [c["command"] for c in setup_wizard.detect(self.repo)["test_command_candidates"]]
        self.assertIn("python3 -m pytest -q", commands)
        self.assertIn("python3 -m unittest discover -s tests", commands)

    def test_it_reports_which_optional_installs_are_already_present(self):
        out = setup_wizard.detect(self.repo)
        self.assertFalse(out["ci"]["conventions"]["workflow"])
        self.assertFalse(out["claude_md"]["exists"])
        self.apply(self.answers(ci=["conventions"], claude_md=True))
        out = setup_wizard.detect(self.repo)
        self.assertTrue(out["ci"]["conventions"]["workflow"])
        self.assertTrue(out["claude_md"]["managed_block"])
        self.assertFalse(out["claude_md"]["malformed"])

    def test_it_writes_nothing(self):
        before = sorted(os.listdir(self.repo))
        setup_wizard.detect(self.repo)
        self.assertEqual(sorted(os.listdir(self.repo)), before)

    def test_a_directory_that_is_not_a_git_repo_still_answers(self):
        """The conversation has to be able to say "not a git repo" — which
        means detect must return rather than raise."""
        out = setup_wizard.detect(self.tmp)
        self.assertTrue(out["ok"])
        self.assertIsNone(out["repo_id"])


class SettingsWriteTest(WizardCase):

    def test_the_split_puts_machine_specific_keys_in_the_local_file(self):
        out = self.apply()
        self.assertTrue(out["ok"], out["errors"])
        project = json.loads(self.read(".acs", "settings.json"))
        local = json.loads(self.read(".acs", "settings.local.json"))
        self.assertEqual(project["ticket_prefix"], "SHOP")
        self.assertNotIn("workspace_path", project)
        self.assertEqual(local["workspace_path"], os.path.join(self.tmp, "ws"))

    def test_user_scope_still_keeps_the_local_file_in_the_repo(self):
        self.apply(self.answers(scope="user"))
        user = json.loads(open(os.path.join(self.home, ".acs", "settings.json"),
                               encoding="utf-8").read())
        self.assertEqual(user["ticket_prefix"], "SHOP")
        self.assertTrue(os.path.exists(os.path.join(self.repo, ".acs", "settings.local.json")))

    def test_a_re_run_preserves_untouched_and_unknown_keys(self):
        """Forward compatibility: an unknown key is legal and is never dropped."""
        self.apply()
        path = os.path.join(self.repo, ".acs", "settings.json")
        doc = json.loads(open(path, encoding="utf-8").read())
        doc["future_key"] = {"set": "by a newer acs"}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        self.apply(self.answers(settings={"merge_strategy": "rebase"}))
        after = json.loads(open(path, encoding="utf-8").read())
        self.assertEqual(after["future_key"], {"set": "by a newer acs"})
        self.assertEqual(after["ticket_prefix"], "SHOP")
        self.assertEqual(after["merge_strategy"], "rebase")

    def test_a_nested_object_is_merged_not_replaced(self):
        """A run that sets tracker.provider must not drop the tracker.github
        block a previous run wrote."""
        self.apply(self.answers(settings={"tracker": {"provider": "github",
                                                      "github": {"owner": "acme"}}}))
        self.apply(self.answers(settings={"tracker": {"provider": "local"}}))
        tracker = json.loads(self.read(".acs", "settings.json"))["tracker"]
        self.assertEqual(tracker["provider"], "local")
        self.assertEqual(tracker["github"], {"owner": "acme"})

    def test_a_re_run_with_the_same_answers_writes_nothing(self):
        self.apply()
        second = self.apply()
        self.assertFalse([c for c in second["changed"] if "settings.json" in c],
                         second["changed"])

    def test_dry_run_reports_and_writes_nothing(self):
        out = self.apply(dry_run=True)
        self.assertTrue(out["dry_run"])
        self.assertTrue(out["changed"])
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".acs", "settings.json")))


class IgnoreTest(WizardCase):

    def test_both_layers_get_both_entries(self):
        self.apply()
        tracked = self.read(".gitignore").splitlines()
        untracked = self.read(".git", "info", "exclude").splitlines()
        for entry in setup_wizard.IGNORE_ENTRIES:
            self.assertIn(entry, tracked)
            self.assertIn(entry, untracked)

    def test_a_re_run_adds_no_duplicate(self):
        self.apply()
        self.apply()
        lines = self.read(".gitignore").splitlines()
        for entry in setup_wizard.IGNORE_ENTRIES:
            self.assertEqual(lines.count(entry), 1, entry)

    def test_an_existing_broader_rule_is_honoured(self):
        with open(os.path.join(self.repo, ".gitignore"), "w", encoding="utf-8") as fh:
            fh.write(".acs/\n")
        out = self.apply()
        self.assertEqual(self.read(".gitignore"), ".acs/\n")
        self.assertTrue(any("already ignored" in line for line in out["unchanged"]))

    def test_a_missing_trailing_newline_cannot_glue_the_entry_on(self):
        with open(os.path.join(self.repo, ".gitignore"), "w", encoding="utf-8") as fh:
            fh.write("*.log")
        self.apply()
        self.assertIn("*.log", self.read(".gitignore").splitlines())
        self.assertIn(".acs/state-machine/", self.read(".gitignore").splitlines())

    def test_a_broad_rule_is_warned_about_never_fixed(self):
        """A `!.acs/` negation is the user's configuration to decide."""
        with open(os.path.join(self.repo, ".gitignore"), "w", encoding="utf-8") as fh:
            fh.write(".acs/\n")
        out = self.apply()
        joined = " | ".join(out["warnings"])
        self.assertIn(".acs/settings.json", joined)
        self.assertIn("narrow the rule", joined)
        self.assertEqual(self.read(".gitignore"), ".acs/\n")


class CiInstallTest(WizardCase):

    def test_each_install_copies_its_files_and_its_workflow(self):
        out = self.apply(self.answers(ci=["conventions", "tests"]))
        for name in ("check-conventions.py", "commit-msg", "pre-push",
                     "install-hooks.sh", "run-tests.py"):
            self.assertTrue(os.path.exists(os.path.join(self.repo, ".acs", "ci", name)), name)
        for workflow in ("acs-conventions.yml", "acs-tests.yml"):
            self.assertTrue(os.path.exists(
                os.path.join(self.repo, ".github", "workflows", workflow)), workflow)
        self.assertIn(".acs/ci/check-conventions.py", out["stage_for_commit"])

    def test_the_scripts_are_installed_executable(self):
        self.apply(self.answers(ci=["conventions"]))
        mode = os.stat(os.path.join(self.repo, ".acs", "ci", "check-conventions.py")).st_mode
        self.assertTrue(mode & 0o111)

    def test_a_re_run_refreshes_rather_than_re_reporting(self):
        """Regenerated on every re-run — so changing a format later and
        re-running refreshes them — but an unchanged copy is not a change."""
        self.apply(self.answers(ci=["conventions"]))
        second = self.apply(self.answers(ci=["conventions"]))
        self.assertFalse([c for c in second["changed"] if "acs-conventions" in c])
        self.assertTrue([c for c in second["unchanged"] if "acs-conventions" in c])

    def test_a_modified_copy_is_restored(self):
        self.apply(self.answers(ci=["conventions"]))
        path = os.path.join(self.repo, ".acs", "ci", "check-conventions.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# tampered\n")
        out = self.apply(self.answers(ci=["conventions"]))
        self.assertTrue([c for c in out["changed"] if "check-conventions" in c])
        self.assertNotIn("# tampered", open(path, encoding="utf-8").read())

    def test_the_required_check_contexts_come_back_for_branch_protection(self):
        out = self.apply(self.answers(ci=["conventions", "tests", "e2e"]))
        self.assertEqual(out["required_check_contexts"],
                         ["Branch / PR / commit conventions", "Tests & coverage", "E2E suite"])

    def test_an_unknown_install_is_a_warning_not_a_crash(self):
        out = self.apply(self.answers(ci=["nope"]))
        self.assertTrue(any("unknown CI install" in w for w in out["warnings"]))


class ClaudeMdTest(WizardCase):

    def _body(self):
        return self.read("CLAUDE.md")

    def test_the_block_is_written_into_a_repo_with_no_claude_md(self):
        self.apply(self.answers(claude_md=True))
        self.assertIn(lib.ACS_BLOCK_BEGIN, self._body())
        self.assertIn("SHOP", self._body())

    def test_a_re_run_replaces_only_the_managed_span(self):
        path = os.path.join(self.repo, "CLAUDE.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# Ours\n\nkeep this\n")
        self.apply(self.answers(claude_md=True))
        self.apply(self.answers(claude_md=True))
        body = self._body()
        self.assertIn("keep this", body)
        self.assertEqual(body.count(lib.ACS_BLOCK_BEGIN), 1)
        self.assertEqual(body.count(lib.ACS_BLOCK_END), 1)

    def test_a_second_run_reports_the_block_as_already_current(self):
        self.apply(self.answers(claude_md=True))
        second = self.apply(self.answers(claude_md=True))
        self.assertTrue([c for c in second["unchanged"] if "CLAUDE.md" in c])

    def test_a_malformed_block_left_by_an_older_run_is_repaired(self):
        path = os.path.join(self.repo, "CLAUDE.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# Ours\n%s\nstale\n%s\n%s\ndoubled\n%s\n"
                     % (lib.ACS_BLOCK_BEGIN, lib.ACS_BLOCK_END,
                        lib.ACS_BLOCK_BEGIN, lib.ACS_BLOCK_END))
        out = self.apply(self.answers(claude_md=True))
        self.assertTrue([c for c in out["changed"] if "repaired" in c], out["changed"])
        self.assertEqual(self._body().count(lib.ACS_BLOCK_BEGIN), 1)

    def test_it_is_not_written_when_the_user_declines(self):
        self.apply(self.answers())
        self.assertFalse(os.path.exists(os.path.join(self.repo, "CLAUDE.md")))


class StatusLineTest(WizardCase):

    def _user_settings(self):
        path = os.path.join(self.home, ".claude", "settings.json")
        return json.loads(open(path, encoding="utf-8").read())

    def test_both_keys_are_written_at_the_chosen_scope(self):
        self.apply(self.answers(status_line={"scope": "user", "statusLine": True,
                                             "subagentStatusLine": True}))
        settings = self._user_settings()
        self.assertIn("statusline.py", settings["statusLine"]["command"])
        self.assertIn("subagent-statusline.py", settings["subagentStatusLine"]["command"])

    def test_an_existing_value_is_never_overwritten(self):
        """`statusLine` is the USER's setting; acs is a guest in that file."""
        path = os.path.join(self.home, ".claude", "settings.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"statusLine": {"type": "command", "command": "mine"}}, fh)
        out = self.apply(self.answers(status_line={"scope": "user", "statusLine": True}))
        self.assertEqual(self._user_settings()["statusLine"]["command"], "mine")
        self.assertTrue([c for c in out["unchanged"] if "already set" in c])

    def test_other_keys_in_that_file_survive(self):
        path = os.path.join(self.home, ".claude", "settings.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"theme": "dark"}, fh)
        self.apply(self.answers(status_line={"scope": "user", "statusLine": True}))
        self.assertEqual(self._user_settings()["theme"], "dark")

    def test_taking_neither_writes_nothing(self):
        self.apply(self.answers(status_line={"scope": "user"}))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude", "settings.json")))


class WorkspaceTest(WizardCase):

    def test_the_partition_is_created_at_the_resolved_root(self):
        self.apply()
        self.assertTrue(os.path.isdir(os.path.join(self.tmp, "ws", "acme-shop")))

    def test_a_re_run_reports_it_as_already_there(self):
        self.apply()
        second = self.apply()
        self.assertTrue([c for c in second["unchanged"] if "already at" in c])

    def test_the_in_repo_default_is_used_when_no_override_is_given(self):
        self.apply({"scope": "project", "settings": {"ticket_prefix": "SHOP"}})
        self.assertTrue(os.path.isdir(
            os.path.join(self.repo, ".acs", "state-machine", "acme-shop")))


class CliTest(WizardCase):

    def _run(self, *args, **kw):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, "acs.py"), "setup"]
                              + list(args), capture_output=True, text=True,
                              cwd=self.repo, env=dict(os.environ, HOME=self.home), **kw)

    def test_detect_is_reachable_as_acs_setup_detect(self):
        out = self._run("detect")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["repo_id"], "acme-shop")

    def test_apply_reads_the_answers_from_a_file(self):
        path = os.path.join(self.tmp, "answers.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.answers(), fh)
        out = self._run("apply", "--answers", path)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(json.loads(out.stdout)["ok"])

    def test_apply_reads_the_answers_from_stdin(self):
        out = self._run("apply", "--answers", "-", input=json.dumps(self.answers()))
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_a_missing_answers_file_is_refused(self):
        out = self._run("apply", "--answers", os.path.join(self.tmp, "nope.json"))
        self.assertEqual(out.returncode, 2)
        self.assertIn("missing or not a JSON object", out.stderr)

    def test_invalid_json_on_stdin_is_refused(self):
        out = self._run("apply", "--answers", "-", input="not json")
        self.assertEqual(out.returncode, 2)
        self.assertIn("invalid JSON", out.stderr)

    def test_the_group_without_a_subcommand_prints_usage(self):
        out = self._run()
        self.assertEqual(out.returncode, 2)
        self.assertIn("usage", out.stderr.lower())


class SkillShapeTest(unittest.TestCase):
    """The other half of the ticket: what the skill is now for."""

    @classmethod
    def setUpClass(cls):
        with open(SKILL, encoding="utf-8") as fh:
            cls.body = fh.read()

    def test_the_skill_reaches_python_only_through_the_two_commands(self):
        """ADR 0001: no Python heredoc, no hand-written JSON dict."""
        self.assertIn("acs.py\" setup detect", self.body)
        self.assertIn("acs.py\" setup apply", self.body)
        self.assertNotIn("python3 - ", self.body)
        self.assertNotIn("import acs_lib", self.body)

    def test_the_mechanics_are_gone(self):
        for gone in ("git check-ignore -q", "info/exclude", "grep -qxF",
                     "upsert_managed_block(existing", "mkdir -p .acs/ci",
                     "chmod +x"):
            self.assertNotIn(gone, self.body, gone)

    def test_the_conversation_is_not(self):
        """Everything a user is told stays: the offers, their defaults, what
        declining costs, and the trade-offs no command can make."""
        for kept in ("Present these as a batch", "### models", "Recommended (default)",
                     "Reasoning effort per role", "always ask", "suites.e2e",
                     "What declining costs", "Completion report (normative)"):
            self.assertIn(kept, self.body, kept)

    def test_it_is_a_quarter_of_its_former_size(self):
        """The ticket asked for <= 200 lines. This lands at 248 because ~90
        lines of the remainder are conversation pinned by six earlier tickets'
        acceptance criteria (MAR-89's models offer, MAR-112/113/117/118's doc
        paths, MAR-114's suites + migration offer, MAR-125's branch-protection
        rules) plus the normative completion report. Cutting to 200 would mean
        deleting things a user is told, which is the opposite of the ticket.
        Pinned here so the number is a decision on the record, not a drift."""
        lines = self.body.count("\n") + 1
        self.assertLessEqual(lines, 250)
        self.assertLess(lines, 1003 // 3, "must stay under a third of the original")


if __name__ == "__main__":
    unittest.main()
