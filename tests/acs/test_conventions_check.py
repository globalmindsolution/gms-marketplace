"""Unit tests for the convention checker that /acs:setup ships into consumer repos.

The checker (plugins/acs/templates/ci/check-conventions.py) runs in the
consumer's CI and as a local pre-push hook with ZERO acs dependencies — only the
Python stdlib — so these tests load it straight from the template path and drive
its pure `evaluate()` core plus the format->regex compiler.

Run:  python3 -m unittest discover -s tests -v
"""

import importlib.util
import json
import os
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKER = os.path.join(REPO_ROOT, "plugins", "acs", "templates", "ci", "check-conventions.py")

_spec = importlib.util.spec_from_file_location("acs_check_conventions", CHECKER)
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)


def settings(**overrides):
    base = {"ticket_prefix": "MAR", "formats": {}}
    base.update(overrides)
    return base


def ctx(branch="task/MAR-12-add-foo", title="[MAR-12] Add foo",
        body=None, labels=None, commits=None):
    if body is None:
        body = "## Summary\nx\n## Ticket\nMAR-12\n## Changes\nx\n## Test plan\nx\n"
    return {
        "branch": branch,
        "title": title,
        "body": body,
        "labels": ["ACS"] if labels is None else labels,
        "commit_subjects": ["MAR-12 add foo"] if commits is None else commits,
    }


def headings(*names):
    return "".join("## %s\n\nbody\n\n" % n for n in names)


class FormatToRegexTests(unittest.TestCase):
    def test_branch_default(self):
        rx = cc.format_to_regex("{type}/{ticket_id}-{slug}", "MAR")
        self.assertTrue(rx.match("task/MAR-12-add-bulk-import"))
        self.assertTrue(rx.match("epic/MAR-1-x"))
        self.assertFalse(rx.match("claude/foo"))
        self.assertFalse(rx.match("task/MAR-12"))          # missing slug
        self.assertFalse(rx.match("task/SHOP-12-x"))       # wrong prefix
        self.assertFalse(rx.match("wip/MAR-12-x"))         # wrong type
        self.assertFalse(rx.match("task/MAR-12-Add_Foo"))  # slug not lower-kebab

    def test_title_default(self):
        rx = cc.format_to_regex("[{ticket_id}] {title}", "MAR")
        self.assertTrue(rx.match("[MAR-3] Product definition (PRD)"))
        self.assertFalse(rx.match("MAR-3 Product definition"))   # no brackets
        self.assertFalse(rx.match("[MAR-3] "))                   # empty title
        self.assertFalse(rx.match("docs: relocate runbook"))

    def test_commit_default(self):
        rx = cc.format_to_regex("{ticket_id} {summary}", "MAR")
        self.assertTrue(rx.match("MAR-7 fix the thing"))
        self.assertFalse(rx.match("fix the thing"))

    def test_custom_prefix_is_escaped(self):
        rx = cc.format_to_regex("[{ticket_id}] {title}", "A.B")
        self.assertTrue(rx.match("[A.B-9] hi"))
        self.assertFalse(rx.match("[AxB-9] hi"))  # '.' is literal, not any-char

    def test_ticket_ref_accepts_local_github_and_jira_shapes(self):
        rx = cc.format_to_regex("[{ticket_ref}] {title}", "MAR")
        self.assertTrue(rx.match("[MAR-80] Render PR title"))   # AC-3 local/unsynced
        self.assertTrue(rx.match("[#161] Render PR title"))     # AC-1 GitHub
        self.assertTrue(rx.match("[ACME-9] Render PR title"))   # AC-2 Jira

    def test_ticket_ref_rejects_malformed_shapes(self):
        rx = cc.format_to_regex("[{ticket_ref}] {title}", "MAR")
        self.assertFalse(rx.match("[] Render PR title"))          # empty bracket content
        self.assertFalse(rx.match("MAR-80 Render PR title"))      # missing brackets
        self.assertFalse(rx.match("[#abc] Render PR title"))      # '#' followed by non-digits
        self.assertFalse(rx.match("[161] Render PR title"))       # bare number, no '#' prefix

    def test_ticket_ref_custom_prefix_is_escaped(self):
        rx = cc.format_to_regex("[{ticket_ref}] {title}", "A.B")
        self.assertTrue(rx.match("[A.B-9] hi"))
        self.assertFalse(rx.match("[AxB-9] hi"))  # '.' is literal, not any-char

    def test_example_ticket_ref_has_no_leaked_token(self):
        example = cc._example("[{ticket_ref}] {title}", "MAR")
        self.assertIn("MAR-12", example)
        self.assertNotIn("{ticket_ref}", example)


class EvaluatePrTests(unittest.TestCase):
    """CI checks one thing (ADR-0106): the PR description names its ticket."""

    def assertPasses(self, res):
        self.assertEqual(res.errors, [], "unexpected errors: %s" % res.errors)
        self.assertIsNone(res.exempt)

    def assertFails(self, res, heading):
        self.assertIn(heading, [h for h, _ in res.errors],
                      "expected a %r error, got %s" % (heading, res.errors))

    def test_a_description_naming_the_ticket_passes(self):
        self.assertPasses(cc.evaluate(settings(), ctx(), "pr"))

    def test_an_issue_reference_or_link_names_a_ticket_too(self):
        for body in ("Closes #161", "See https://github.com/acme/shop/issues/161"):
            with self.subTest(body=body):
                self.assertPasses(cc.evaluate(settings(), ctx(body=body), "pr"))

    def test_a_description_naming_no_ticket_fails(self):
        for body in ("", "## Summary\nAdd foo\n", "Fixes the thing, step #one"):
            with self.subTest(body=body):
                self.assertFails(cc.evaluate(settings(), ctx(body=body), "pr"), "ticket_link")

    def test_look_alikes_do_not_count(self):
        """Another repo's prefix, an HTML entity and a URL fragment are not a
        ticket reference."""
        for body in ("SHOP-12", "caf&#233;", "docs/page#3"):
            with self.subTest(body=body):
                self.assertFails(cc.evaluate(settings(), ctx(body=body), "pr"), "ticket_link")

    def test_branch_title_label_and_commits_are_not_checked(self):
        """What CI used to check and no longer does: a PR opened from any
        branch, with any title, no label and any commit subjects passes as
        long as its description names the ticket."""
        s = settings(formats={"pr_title": "[{ticket_id}] {title}"},
                     enforcement={"checks": {"commit_message": True, "pr_title": True,
                                             "acs_label": True, "pr_description": True}})
        res = cc.evaluate(s, ctx(branch="claude/whatever", title="wip", labels=[],
                                 commits=["wip"], body="Work for MAR-12"), "pr")
        self.assertPasses(res)
        self.assertEqual(res.skipped, [])

    def test_the_only_pr_mode_check_is_the_ticket_link(self):
        self.assertEqual(cc.MODE_CHECKS["pr"], ["ticket_link"])


class ExemptionTests(unittest.TestCase):
    def test_exempt_label_skips_everything(self):
        res = cc.evaluate(settings(), ctx(branch="whatever", title="nope",
                                          labels=["acs-exempt"], commits=["wip"]), "pr")
        self.assertIsNotNone(res.exempt)
        self.assertEqual(res.errors, [])

    def test_exempt_branch_glob_skips(self):
        res = cc.evaluate(settings(), ctx(branch="release/v1.2.0", title="nope", labels=[]), "pr")
        self.assertIsNotNone(res.exempt)
        self.assertEqual(res.errors, [])

    def test_custom_exempt_config(self):
        s = settings(enforcement={"exempt_branches": ["hotfix/*"], "exempt_label": "skip-acs"})
        self.assertIsNotNone(cc.evaluate(s, ctx(branch="hotfix/x", labels=[]), "pr").exempt)
        self.assertIsNotNone(cc.evaluate(s, ctx(branch="b", labels=["skip-acs"]), "pr").exempt)
        # the built-in release/* no longer applies once overridden
        self.assertIsNone(cc.evaluate(s, ctx(branch="release/x", labels=[],
                                             title="bad", commits=[]), "pr").exempt)


class DefaultsAndMalformedSettingsTests(unittest.TestCase):
    """ADR-0105: absent keys take the plugin's defaults; malformed ones fail."""

    def test_no_settings_checks_against_the_default_prefix(self):
        self.assertEqual(cc.evaluate({}, ctx(body="ACS-12"), "pr").errors, [])

    def test_the_default_prefix_is_enforced(self):
        res = cc.evaluate({}, ctx(body="MAR-12"), "pr")
        self.assertIn("ticket_link", [h for h, _ in res.errors])

    def test_the_default_formats_apply_to_the_local_hooks(self):
        res = cc.evaluate({}, ctx(branch="task/ACS-12-add-foo"), "pre-push")
        self.assertEqual(res.errors, [])

    def test_malformed_prefix_fails_closed(self):
        self.assertFails_settings(cc.evaluate({"ticket_prefix": "mar"}, ctx(), "pr"))

    def test_non_object_formats_fails_closed(self):
        self.assertFails_settings(cc.evaluate({"formats": "x"}, ctx(), "pr"))

    def assertFails_settings(self, res):
        self.assertIn("settings", [h for h, _ in res.errors])


class PrePushModeTests(unittest.TestCase):
    def test_prepush_checks_branch_only_by_default(self):
        # bad title/body/labels are ignored in pre-push; branch is fine -> passes
        res = cc.evaluate(settings(), ctx(branch="task/MAR-12-x", title="bad",
                                          body="", labels=[]), "pre-push")
        self.assertEqual(res.errors, [])

    def test_prepush_flags_bad_branch(self):
        res = cc.evaluate(settings(), ctx(branch="wip", title="bad"), "pre-push")
        self.assertIn("branch_name", [h for h, _ in res.errors])

    def test_prepush_runs_commit_check_when_enabled(self):
        s = settings(enforcement={"checks": {"commit_message": True}})
        res = cc.evaluate(s, ctx(branch="task/MAR-12-x", commits=["nope"]), "pre-push")
        self.assertIn("commit_message", [h for h, _ in res.errors])


class PrePushRangeTests(unittest.TestCase):
    """What the pre-push hook reads for a branch the remote does not have yet."""

    def test_a_new_branch_is_judged_on_its_own_commits_only(self):
        """It used to run `git log <sha>` over the whole history, so with the
        commit check on, main's plain squash subjects (ADR-0105) refused every
        first push of every branch."""
        import io, shutil, subprocess, tempfile
        repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, repo, True)
        git = lambda *a: subprocess.run(["git", "-C", repo, "-c", "user.email=e@x",
                                         "-c", "user.name=e"] + list(a),
                                        check=True, capture_output=True, text=True).stdout
        git("init", "-q", "-b", "main")
        git("commit", "-q", "--allow-empty", "-m", "Add wishlist support (#12)")
        git("update-ref", "refs/remotes/origin/main", "HEAD")
        git("checkout", "-q", "-b", "task/MAR-13-x")
        git("commit", "-q", "--allow-empty", "-m", "MAR-13 add x")
        head = git("rev-parse", "HEAD").strip()
        push = "refs/heads/task/MAR-13-x %s refs/heads/task/MAR-13-x %s\n" % (head, "0" * 40)
        with mock.patch("sys.stdin", io.StringIO(push)):
            self.assertEqual(cc._commit_subjects_prepush(repo), ["MAR-13 add x"])


class DisabledChecksTests(unittest.TestCase):
    def test_disabling_a_local_check_skips_it(self):
        s = settings(enforcement={"checks": {"branch_name": False}})
        res = cc.evaluate(s, ctx(branch="totally wrong"), "pre-push")
        self.assertEqual(res.errors, [])
        self.assertIn("branch_name", res.skipped)

    def test_the_ticket_link_is_not_a_toggle(self):
        s = settings(enforcement={"checks": {"ticket_link": False}})
        self.assertIn("ticket_link",
                      [h for h, _ in cc.evaluate(s, ctx(body="none"), "pr").errors])


class CommitMsgModeTests(unittest.TestCase):
    """The commit-msg hook checks only the commit subject, against the configured
    formats.commit_message — never the branch/title/label (unknown at commit)."""

    def test_commit_check_off_by_default_passes(self):
        res = cc.evaluate(settings(), ctx(commits=["wip"]), "commit-msg")
        self.assertEqual(res.errors, [])

    def test_bad_subject_fails_when_enabled(self):
        s = settings(enforcement={"checks": {"commit_message": True}})
        self.assertIn("commit_message",
                      [h for h, _ in cc.evaluate(s, ctx(commits=["wip"]), "commit-msg").errors])

    def test_good_subject_passes_when_enabled(self):
        s = settings(enforcement={"checks": {"commit_message": True}})
        self.assertEqual(cc.evaluate(s, ctx(commits=["MAR-9 do the thing"]), "commit-msg").errors, [])

    def test_uses_configured_commit_format(self):
        # A repo that configured a different commit_message format is honoured.
        s = settings(formats={"commit_message": "{type}: {summary}"},
                     enforcement={"checks": {"commit_message": True}})
        self.assertEqual(cc.evaluate(s, ctx(commits=["task: ship it"]), "commit-msg").errors, [])
        self.assertIn("commit_message",
                      [h for h, _ in cc.evaluate(s, ctx(commits=["MAR-9 nope"]), "commit-msg").errors])

    def test_does_not_check_branch_or_title(self):
        s = settings(enforcement={"checks": {"commit_message": True, "branch_name": True}})
        res = cc.evaluate(s, ctx(branch="garbage", title="garbage",
                                 commits=["MAR-9 ok"]), "commit-msg")
        self.assertEqual(res.errors, [])  # branch_name not in commit-msg mode

    def test_merge_subject_ignored(self):
        s = settings(enforcement={"checks": {"commit_message": True}})
        self.assertEqual(cc.evaluate(s, ctx(commits=["Merge branch 'main'"]), "commit-msg").errors, [])

    def test_exempt_branch_skips(self):
        s = settings(enforcement={"checks": {"commit_message": True}})
        res = cc.evaluate(s, ctx(branch="release/v1", commits=["wip"]), "commit-msg")
        self.assertIsNotNone(res.exempt)
        self.assertEqual(res.errors, [])


class ReadCommitSubjectTests(unittest.TestCase):
    def test_skips_comments_and_blanks(self):
        import tempfile, os
        fd, path = tempfile.mkstemp()
        os.close(fd)
        self.addCleanup(os.unlink, path)
        with open(path, "w") as fh:
            fh.write("\n# a comment\nMAR-9 real subject\n# more\nbody line\n")
        self.assertEqual(cc._read_commit_subject(path), "MAR-9 real subject")


class DefaultsMatchThePluginTest(unittest.TestCase):
    """The checker runs without the plugin, so it carries its own copy of the
    defaults. The two copies had drifted (a `[{ticket_ref}] {title}` PR title
    here against `[{ticket_id}] {title}` in the plugin); this is what keeps the
    ones it still reads level."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts"))
        import acs_lib
        cls.lib = acs_lib

    def test_the_ticket_prefix_default_matches(self):
        self.assertEqual(cc.DEFAULT_TICKET_PREFIX, self.lib.DEFAULT_TICKET_PREFIX)

    def test_every_format_default_matches(self):
        for key, value in cc.FORMAT_DEFAULTS.items():
            with self.subTest(format=key):
                self.assertEqual(value, self.lib.DEFAULT_SETTINGS["formats"][key])

    def test_the_schema_documents_the_same_defaults(self):
        with open(os.path.join(REPO_ROOT, "plugins", "acs", "schemas",
                               "settings.schema.json"), encoding="utf-8") as fh:
            props = json.load(fh)["properties"]
        self.assertEqual(props["ticket_prefix"]["default"], self.lib.DEFAULT_TICKET_PREFIX)
        for key in cc.FORMAT_DEFAULTS:
            default = props["formats"]["properties"][key].get("default")
            if default is not None:
                with self.subTest(format=key):
                    self.assertEqual(default, self.lib.DEFAULT_SETTINGS["formats"][key])

    def test_every_shared_enforcement_default_matches(self):
        shared = set(cc.ENFORCEMENT_DEFAULTS) & set(self.lib.ENFORCEMENT_DEFAULTS)
        self.assertTrue(shared)
        for key in sorted(shared):
            with self.subTest(key=key):
                self.assertEqual(cc.ENFORCEMENT_DEFAULTS[key], self.lib.ENFORCEMENT_DEFAULTS[key])

    def test_this_repos_installed_copy_is_the_template(self):
        installed = os.path.join(REPO_ROOT, ".acs", "ci", "check-conventions.py")
        with open(CHECKER, "rb") as a, open(installed, "rb") as b:
            self.assertEqual(a.read(), b.read(),
                             ".acs/ci/check-conventions.py is a copy of the template; "
                             "re-copy it rather than editing it")


if __name__ == "__main__":
    unittest.main()
